from langchain_chroma import Chroma
from utils.config_handler import chroma_conf
from model.factor import get_embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import os

from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import loggers
from utils.path_tool import get_abs_path


def _get_splitter(category: str) -> RecursiveCharacterTextSplitter:
    """根据文档分类获取对应的分块器，未配置则使用默认值。"""
    strategies = chroma_conf.get("chunk_strategies", {})
    strategy = strategies.get(category, {})
    return RecursiveCharacterTextSplitter(
        chunk_size=strategy.get("chunk_size", chroma_conf.get("chunk_size", 200)),
        chunk_overlap=strategy.get("chunk_overlap", chroma_conf.get("chunk_overlap", 20)),
        separators=strategy.get("separators", chroma_conf.get("separators", ["\n\n", "\n", "。"])),
        length_function=len,
    )


class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            persist_directory=chroma_conf["persist_directory"],
            embedding_function=get_embed_model(),
        )
        # 默认分块器（兼容旧逻辑）
        self.spliter = _get_splitter("")

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def search_with_scores(self, query: str, k: int | None = None) -> list[tuple[Document, float]]:
        k = k or chroma_conf.get("k", 3)
        return self.vector_store.similarity_search_with_score(query, k=k)

    def get_status(self) -> dict:
        try:
            collection = self.vector_store._collection
            chunk_count = collection.count()
        except Exception:
            chunk_count = -1

        try:
            categories = set()
            result = collection.get(include=["metadatas"])
            if result and result.get("metadatas"):
                for meta in result["metadatas"]:
                    cat = meta.get("category", "")
                    if cat:
                        categories.add(cat)
        except Exception:
            categories = set()

        return {
            "chunk_count": chunk_count,
            "categories": sorted(categories),
            "collection_name": chroma_conf.get("collection_name", ""),
            "persist_directory": chroma_conf.get("persist_directory", ""),
            "k": chroma_conf.get("k", 3),
        }

    def get_detailed_structure(self) -> dict:
        """获取知识库详细内容结构：按分类 -> 按来源文件 -> chunk 列表。"""
        try:
            collection = self.vector_store._collection
            result = collection.get(include=["metadatas", "documents"])
        except Exception as e:
            return {"error": str(e), "chunk_count": -1, "categories": []}

        chunk_count = len(result.get("ids", [])) if result else 0
        metadatas = result.get("metadatas") or []
        documents = result.get("documents") or []
        ids = result.get("ids") or []

        # 按分类 → 来源文件 组织
        from collections import defaultdict
        category_map: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

        for i, chunk_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            doc_text = documents[i] if i < len(documents) else ""
            category = meta.get("category", "未分类")
            source = meta.get("source", "未知来源")
            # 取简短文件名
            short_source = source.split("\\")[-1].split("/")[-1] if source else "未知"
            category_map[category][short_source].append({
                "chunk_id": chunk_id,
                "content_preview": doc_text[:120] + ("..." if len(doc_text) > 120 else ""),
                "char_count": len(doc_text),
                "metadata": {k: v for k, v in meta.items() if k not in ("source", "category")},
            })

        # 构建结构化输出
        categories_detail = []
        for cat_name in sorted(category_map.keys()):
            cat_entry = {
                "name": cat_name,
                "file_count": len(category_map[cat_name]),
                "total_chunks": sum(len(chunks) for chunks in category_map[cat_name].values()),
                "files": [],
            }
            for file_name in sorted(category_map[cat_name].keys()):
                chunks = category_map[cat_name][file_name]
                # 取第一个 chunk 的 source 作为完整路径
                full_source = chunks[0]["metadata"].get("source", "")
                cat_entry["files"].append({
                    "name": file_name,
                    "source": full_source,
                    "chunk_count": len(chunks),
                    "total_chars": sum(c["char_count"] for c in chunks),
                    "chunks": sorted(chunks, key=lambda c: c["chunk_id"]),
                })
            categories_detail.append(cat_entry)

        # MD5 记录
        md5_records = self._read_md5_records()
        tracked_files = [k for k in md5_records.keys() if not k.startswith("__legacy__")]

        return {
            "chunk_count": chunk_count,
            "category_count": len(categories_detail),
            "tracked_file_count": len(tracked_files),
            "collection_name": chroma_conf.get("collection_name", ""),
            "categories": categories_detail,
        }

    # ── MD5 记录管理（文件路径 + MD5 组合键）──

    def _md5_store_path(self) -> str:
        return get_abs_path(chroma_conf["md5_hex_store"])

    def _read_md5_records(self) -> dict[str, str]:
        """读取 MD5 记录，返回 {文件路径: MD5} 字典。"""
        records = {}
        store = self._md5_store_path()
        if not os.path.exists(store):
            return records
        with open(store, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # 格式: file_path|md5  或  旧格式: md5
                if "|" in line:
                    parts = line.rsplit("|", 1)
                    records[parts[0]] = parts[1]
                else:
                    # 兼容旧格式：只有 MD5，路径不可知
                    records[f"__legacy__{line}"] = line
        return records

    def _write_md5_record(self, file_path: str, md5: str):
        store = self._md5_store_path()
        with open(store, "a", encoding="utf-8") as f:
            f.write(f"{file_path}|{md5}\n")

    def _remove_md5_record(self, file_path: str):
        records = self._read_md5_records()
        records.pop(file_path, None)
        store = self._md5_store_path()
        with open(store, "w", encoding="utf-8") as f:
            for path, md5 in records.items():
                if path.startswith("__legacy__"):
                    f.write(f"{md5}\n")
                else:
                    f.write(f"{path}|{md5}\n")

    # ── 文档增删改 ──

    def delete_by_source(self, file_path: str):
        """按来源文件路径删除向量库中对应的所有 chunk。"""
        try:
            collection = self.vector_store._collection
            result = collection.get(where={"source": file_path})
            ids = result.get("ids", [])
            if ids:
                collection.delete(ids=ids)
                loggers.info(f"已删除 {len(ids)} 条向量，来源: {file_path}")
            self._remove_md5_record(file_path)
        except Exception as e:
            loggers.error(f"删除文档失败:{file_path}, 错误:{e}")

    def update_chunk(self, chunk_id: str, new_content: str) -> bool:
        """更新单个 chunk 的内容，Chroma 会自动重新嵌入。"""
        try:
            collection = self.vector_store._collection
            # 验证 chunk 存在
            result = collection.get(ids=[chunk_id], include=["metadatas"])
            if not result or not result.get("ids"):
                loggers.error(f"chunk 不存在: {chunk_id}")
                return False
            # 更新文档内容，Chroma 会重新计算 embedding
            collection.update(ids=[chunk_id], documents=[new_content])
            loggers.info(f"chunk 已更新: {chunk_id} 内容长度: {len(new_content)}")
            return True
        except Exception as e:
            loggers.error(f"更新 chunk 失败: {chunk_id}, 错误: {e}")
            return False

    def update_document(self, file_path: str, category: str):
        """更新单个文档：先删旧的，再加新的。"""
        self.delete_by_source(file_path)
        self._load_single_file(file_path, category)

    def _load_single_file(self, file_path: str, category: str):
        """加载单个文件到向量库。"""
        # 检查是否支持的文件类型
        ext = os.path.splitext(file_path)[1]
        if ext not in chroma_conf["allow_knowledge_file_type"]:
            loggers.error(f"不支持的文件类型:{file_path}")
            return

        # 计算 MD5
        md5_hex = get_file_md5_hex(file_path)
        if not md5_hex:
            return

        # 检查是否已加载（同一路径同一 MD5 跳过）
        records = self._read_md5_records()
        if records.get(file_path) == md5_hex:
            loggers.info(f"内容未变，跳过:{file_path}")
            return

        # 如果路径已存在但 MD5 不同 → 更新
        if file_path in records:
            loggers.info(f"检测到文件变化，更新:{file_path}")
            self.delete_by_source(file_path)

        # 加载文档
        if file_path.endswith(".pdf"):
            documents = pdf_loader(file_path)
        elif file_path.endswith(".txt"):
            documents = txt_loader(file_path)
        else:
            return

        if not documents:
            loggers.error(f"无内容:{file_path}")
            return

        # 注入元数据
        for doc in documents:
            doc.metadata["category"] = category
            if "source" not in doc.metadata:
                doc.metadata["source"] = file_path

        # 按分类选择分块策略
        spliter = _get_splitter(category)
        texts = spliter.split_documents(documents)
        if not texts:
            loggers.error(f"分片后无内容:{file_path}")
            return

        # 写入向量库
        self.vector_store.add_documents(texts)
        self._write_md5_record(file_path, md5_hex)
        loggers.info(f"内容已添加:{file_path} 分类:{category} chunks:{len(texts)}")

    def load_document(self):
        """扫描 data 目录，增量加载/更新所有文档。"""
        loggers.info("开始加载文档...")

        data_path = get_abs_path(chroma_conf["data_path"])
        loggers.info(f"数据目录：{data_path}")
        loggers.info(f"允许的文件类型：{chroma_conf['allow_knowledge_file_type']}")

        allowed_files = listdir_with_allowed_type(
            data_path,
            tuple(chroma_conf["allow_knowledge_file_type"])
        )
        if not allowed_files:
            loggers.error(f"未找到任何文件，请检查目录：{data_path}")
            return

        loggers.info(f"找到 {len(allowed_files)} 个文件待处理")

        # 先清理已删除的文件
        current_paths = {os.path.abspath(p) for p, _ in allowed_files}
        records = self._read_md5_records()
        for record_path in list(records.keys()):
            if record_path.startswith("__legacy__"):
                continue
            if record_path not in current_paths:
                loggers.info(f"文件已删除，清理向量:{record_path}")
                self.delete_by_source(record_path)

        # 加载/更新所有文件
        for path, category in allowed_files:
            abs_path = os.path.abspath(path)
            try:
                self._load_single_file(abs_path, category)
            except Exception as e:
                loggers.error(f"加载内容出错:{abs_path},错误信息:{e}")


if __name__ == "__main__":
    # VectorStoreService().load_document()
    retriever = VectorStoreService().get_retriever()
    result = retriever.invoke("WIFI")
    for r in result:
        print(r.page_content)
        print("-" * 20)
