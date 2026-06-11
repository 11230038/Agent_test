from abc import ABC, abstractmethod
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_community.chat_models.tongyi import BaseChatModel
from typing import Optional
from utils.config_handler import rag_conf, api_conf


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> BaseChatModel:
        api_key = api_conf.get("dashscope_api_key")

        if not api_key:
            raise ValueError(
                "DashScope API key not found. Please set it in config/api.yml"
            )

        model_name = api_conf.get("chat_model_name") or rag_conf.get("chat_model_name", "qwen3-max")

        return ChatTongyi(
            model=model_name,
            dashscope_api_key=api_key,
            streaming=True,
            request_timeout=120,
        )


class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Embeddings:
        api_key = api_conf.get("dashscope_api_key")

        if not api_key:
            raise ValueError(
                "DashScope API key not found. Please set it in config/api.yml"
            )

        model_name = api_conf.get("embedding_model_name") or rag_conf.get("embedding_model_name",
                                                                          "text-embedding-v4")

        return DashScopeEmbeddings(model=model_name, dashscope_api_key=api_key)


_chat_model: BaseChatModel | None = None
_embed_model: Embeddings | None = None


def get_chat_model() -> BaseChatModel:
    global _chat_model
    if _chat_model is None:
        try:
            _chat_model = ChatModelFactory().generator()
        except Exception as e:
            raise RuntimeError(f"聊天模型初始化失败:{e}") from e
    return _chat_model


def get_embed_model() -> Embeddings:
    global _embed_model
    if _embed_model is None:
        try:
            _embed_model = EmbeddingModelFactory().generator()
        except Exception as e:
            raise RuntimeError(f"向量模型初始化失败:{e}") from e
    return _embed_model
