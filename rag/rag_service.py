from utils .prompt_loader import load_rag_prompts
from rag.vector_store import VectorStoreService
from langchain_core.prompts import PromptTemplate
from model.factor import chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document


class RagSummarizeService:
    # RAG(检索增强生成) 服务类，负责从向量库检索文档并生成摘要
    def __init__(self):
        self.vector_store=VectorStoreService() # 创建向量存储服务实例
        self.retriever=self.vector_store.get_retriever() # 获取文档检索器
        self.prompt_text = load_rag_prompts() # 加载 RAG 提示词模板
        self.prompt_template=PromptTemplate.from_template(self.prompt_text) # 创建提示词模板对象
        self.model=chat_model # 获取聊天模型实例
        self.chain=self._init_chain()
    def _init_chain(self):
        # 处理流程：提示词模板 → 语言模型 → 字符串解析器
        chain=self.prompt_template|self.model|StrOutputParser()
        return chain

    def retriever_docs(self,query:str)->list[Document]:
        # 根据查询检索相关文档
        # Args:
        #     query (str): 用户的查询语句
        # Returns:
        #     list[Document]: 检索到的文档列表，包含内容和元数据
        return self.retriever.invoke(query)

    def rag_summarize(self,query:str)->str:
        # 执行完整的 RAG 流程：检索文档并生成摘要回答
        # Args:
        #     query (str): 用户的查询语句
        # Returns:
        #     str: 模型生成的摘要回答

        # 步骤 1: 检索相关文档
        docs=self.retriever_docs(query)
        if not docs:
            return "未检索到相关参考资料。"

        # 步骤 2: 构建上下文字符串
        counter=0
        context=""
        for doc in docs:
            counter+=1
            # 格式化每个参考资料，包含文档内容和元数据（如来源文件、页码等）
            context+=f"参考资料{counter}：参考资料内容{doc.page_content}|参考元数据{doc.metadata}\n"
        # 步骤 3: 调用处理链生成回答
        # 将上下文和原始查询输入模型，模型根据提示词模板生成回答
        return self.chain.invoke({"context":context,"input":query})

rag=RagSummarizeService()

if __name__=="__main__":
    rag_service=RagSummarizeService()
    print(rag_service.rag_summarize("大户型选择机器人推荐"))
