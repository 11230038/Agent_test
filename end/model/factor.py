from abc import ABC, abstractmethod
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_community.chat_models.tongyi import BaseChatModel
from typing import Optional
from utils.config_handler import rag_conf, agent_conf


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> BaseChatModel:
        # Get API key from config or environment variable
        api_key = agent_conf.get("api", {}).get("dashscope_api_key")

        if not api_key:
            raise ValueError(
                "DashScope API key not found. Please set it in config/agent.yml "
                "or environment variable DASHSCOPE_API_KEY"
            )

        # Get model name from agent config (priority) or rag config
        model_name = agent_conf.get("api", {}).get("chat_model_name") or rag_conf.get("chat_model_name", "qwen3-max")

        return ChatTongyi(model=model_name, dashscope_api_key=api_key)


class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Embeddings:
        # Get API key from config or environment variable
        api_key = agent_conf.get("api", {}).get("dashscope_api_key")

        if not api_key:
            raise ValueError(
                "DashScope API key not found. Please set it in config/agent.yml "
                "or environment variable DASHSCOPE_API_KEY"
            )

        # Get model name from agent config (priority) or rag config
        model_name = agent_conf.get("api", {}).get("embedding_model_name") or rag_conf.get("embedding_model_name",
                                                                                           "text-embedding-v4")

        return DashScopeEmbeddings(model=model_name, dashscope_api_key=api_key)


chat_model = ChatModelFactory().generator()
embed_model = EmbeddingModelFactory().generator()
