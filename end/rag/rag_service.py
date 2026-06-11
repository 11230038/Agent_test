import time
import threading
import re
from collections import OrderedDict
from dataclasses import dataclass

from utils.prompt_loader import load_rag_prompts
from rag.vector_store import VectorStoreService
from langchain_core.prompts import PromptTemplate
from model.factor import get_chat_model, get_embed_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from utils.logger_handler import loggers

# 相似度阈值：低于此分数的文档会被过滤掉（0-1，越高越严）
SIMILARITY_THRESHOLD = 0.3

# 上下文格式化策略
CONTEXT_STYLES = {
    "full": "参考资料{idx}：内容{doc.page_content} | 元数据{doc.metadata}",
    "compact": "【资料{idx}】{doc.page_content}",
    "sources": "【来源{idx}】{doc.page_content}\n  └ 文件: {source} | 分类: {category}",
}


@dataclass
class RetrievalCacheStats:
    hits: int = 0
    misses: int = 0
    size: int = 0


class RetrievalCache:
    """简单的内存检索缓存，相同 query 直接返回缓存结果，避免重复 embedding 调用。"""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self._cache: OrderedDict[str, tuple[float, list[Document]]] = OrderedDict()
        self._lock = threading.Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.stats = RetrievalCacheStats()

    def _normalize(self, query: str) -> str:
        return query.strip().lower()

    def get(self, query: str) -> list[Document] | None:
        key = self._normalize(query)
        with self._lock:
            if key not in self._cache:
                self.stats.misses += 1
                self.stats.size = len(self._cache)
                return None
            ts, docs = self._cache[key]
            if time.time() - ts > self.ttl_seconds:
                del self._cache[key]
                self.stats.misses += 1
                self.stats.size = len(self._cache)
                return None
            self._cache.move_to_end(key)
            self.stats.hits += 1
            self.stats.size = len(self._cache)
            return docs

    def set(self, query: str, docs: list[Document]):
        key = self._normalize(query)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (time.time(), docs)
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self.stats = RetrievalCacheStats()


def _tokenize_chinese(text: str) -> set[str]:
    tokens = set(re.findall(r"[一-鿿]{2,}", text.lower()))
    tokens.update(re.findall(r"[a-zA-Z]{2,}", text.lower()))
    return tokens


def _keyword_boost(query: str, docs_with_scores: list[tuple[Document, float]]) -> list[tuple[Document, float]]:
    query_tokens = _tokenize_chinese(query)
    if not query_tokens:
        return docs_with_scores

    boosted = []
    for doc, score in docs_with_scores:
        doc_tokens = _tokenize_chinese(doc.page_content)
        overlap = len(query_tokens & doc_tokens)
        if overlap > 0:
            bonus = min(overlap * 0.02, 0.15)
            boosted.append((doc, score + bonus))
        else:
            boosted.append((doc, score))
    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted


def _dynamic_k(query: str, base_k: int = 3) -> int:
    query_len = len(query)
    if query_len <= 8:
        return 2
    elif query_len >= 30:
        return min(base_k + 2, 6)
    return base_k


def _extract_source(doc: Document) -> str:
    source = doc.metadata.get("source", "")
    return source.split("\\")[-1].split("/")[-1] if source else "未知"


class RagSummarizeService:

    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompts()
        if not self.prompt_text:
            raise ValueError("RAG 提示词加载失败")
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = get_chat_model()
        self.chain = self._init_chain()
        self.retrieval_cache = RetrievalCache(max_size=100, ttl_seconds=300)

    def _init_chain(self):
        return self.prompt_template | self.model | StrOutputParser()

    # ── 1. 检索（独立复用）──

    def search(self, query: str) -> list[dict]:
        """检索相关文档，返回结构化结果（文档内容 + 分数 + 来源）。"""
        k = _dynamic_k(query)
        docs_with_scores = self.vector_store.search_with_scores(query, k)
        docs_with_scores = _keyword_boost(query, docs_with_scores)
        accepted = [(d, s) for d, s in docs_with_scores if s >= SIMILARITY_THRESHOLD]

        if docs_with_scores:
            scores = [s for _, s in docs_with_scores]
            loggers.info(
                f"RAG检索: query='{query[:40]}' k={k} "
                f"total={len(docs_with_scores)} accepted={len(accepted)} "
                f"discarded={len(docs_with_scores) - len(accepted)} "
                f"max_score={max(scores):.3f} min_score={min(scores):.3f}"
            )

        results = []
        for doc, score in accepted:
            results.append({
                "content": doc.page_content,
                "score": round(score, 4),
                "source": _extract_source(doc),
                "category": doc.metadata.get("category", ""),
                "metadata": doc.metadata,
            })
        return results

    # ── 2. 格式化上下文（多种策略）──

    def format_context(self, search_results: list[dict], style: str = "full") -> str:
        """将检索结果格式化为 LLM 上下文。"""
        template = CONTEXT_STYLES.get(style, CONTEXT_STYLES["full"])
        parts = []
        for idx, item in enumerate(search_results, 1):
            # 构造一个临时 Document 对象用于模板渲染
            doc = Document(
                page_content=item["content"],
                metadata=item["metadata"],
            )
            source = item["source"]
            category = item["category"]
            parts.append(
                template.format(
                    idx=idx,
                    doc=doc,
                    source=source,
                    category=category,
                )
            )
        return "\n".join(parts)

    # ── 3. 生成回答（独立复用）──

    def generate(self, context: str, query: str) -> str:
        """基于上下文和问题生成回答。"""
        return self.chain.invoke({"context": context, "input": query})

    # ── 便捷方法（向后兼容）──

    def retriever_docs(self, query: str) -> list[Document]:
        cached = self.retrieval_cache.get(query)
        if cached is not None:
            return cached
        results = self.search(query)
        docs = [Document(page_content=r["content"], metadata=r["metadata"]) for r in results]
        if docs:
            self.retrieval_cache.set(query, docs)
        return docs

    def rag_summarize(self, query: str, style: str = "full") -> str:
        results = self.search(query)
        if not results:
            return "未检索到相关参考资料。"
        context = self.format_context(results, style=style)
        return self.generate(context, query)

    def cache_stats(self) -> RetrievalCacheStats:
        return self.retrieval_cache.stats

    def get_status(self) -> dict:
        vector_status = self.vector_store.get_status()
        cache = self.cache_stats()

        embedding_ok = True
        embedding_error = None
        try:
            get_embed_model()
        except Exception as e:
            embedding_ok = False
            embedding_error = str(e)

        hit_rate = 0.0
        total = cache.hits + cache.misses
        if total > 0:
            hit_rate = round(cache.hits / total, 3)

        return {
            "knowledge_base": {
                "chunk_count": vector_status["chunk_count"],
                "categories": vector_status["categories"],
                "collection_name": vector_status["collection_name"],
            },
            "cache": {
                "hits": cache.hits,
                "misses": cache.misses,
                "size": cache.size,
                "hit_rate": hit_rate,
            },
            "embedding": {
                "available": embedding_ok,
                "error": embedding_error,
            },
            "retrieval": {
                "k": vector_status["k"],
                "similarity_threshold": SIMILARITY_THRESHOLD,
            },
        }


_rag_service: RagSummarizeService | None = None


def get_rag_service() -> RagSummarizeService:
    global _rag_service
    if _rag_service is None:
        try:
            _rag_service = RagSummarizeService()
        except Exception as e:
            raise RuntimeError(f"RAG 服务初始化失败:{e}") from e
    return _rag_service


if __name__ == "__main__":
    rag_service = get_rag_service()
    print(rag_service.rag_summarize("大户型选择机器人推荐"))
