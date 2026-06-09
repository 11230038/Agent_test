from langchain_chroma import Chroma
from utils.config_handler import chroma_conf
from model.factor import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import os

from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import loggers
from utils.path_tool import get_abs_path

class VectorStoreService:
    def __init__(self):
        # 初始化向量存储和文本分片器
        self.vector_store=Chroma(
            collection_name=chroma_conf["collection_name"],# 向量集合名称，从配置文件读取
            persist_directory=chroma_conf["persist_directory"],# 持久化目录，从配置文件读取
            embedding_function=embed_model# 嵌入模型，从配置文件读取
        )
        self.spliter=RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],# 分片大小，从配置文件读取
            chunk_overlap=chroma_conf["chunk_overlap"],# 分片重叠，从配置文件读取
            separators=chroma_conf["separators"],# 分隔符，从配置文件读取
            length_function=len,
        )
    def get_retriever(self):
        # 获取向量检索器，用于根据查询检索相关文档
        # search_kwargs={"k": 3} 表示每次检索返回最相关的 3 个结果
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    def load_document(self):
        # 加载知识文档到向量数据库的核心方法
        # 支持 PDF 和 TXT 文件格式，自动去重（基于 MD5）
        loggers.info("开始加载文档...")
        def check_md5_hex(md5_for_check:str):
            # 检查文件 MD5 是否已存在于记录文件中，用于避免重复加载相同内容
            # Args:
            #     md5_for_check (str): 待检查的文件 MD5 值
            # Returns:
            #     bool: 如果 MD5 已存在返回 True，否则返回 False

            # 如果 MD5 记录文件不存在，创建空文件并返回 False（表示未存在）
           if not os.path.exists(get_abs_path(chroma_conf["md5_hex_store"])):
               open(get_abs_path(chroma_conf["md5_hex_store"]),"w",encoding="utf-8").close()
               return False

            # 遍历 MD5 记录文件，检查是否已有该 MD5
           with open(get_abs_path(chroma_conf["md5_hex_store"]),"r",encoding="utf-8") as f:
               for line in f.readlines():
                   line=line.strip()
                   if line==md5_for_check:
                       return True
           return False
        def save_md5(md5_for_save:str):
            # 将新的文件 MD5 保存到记录文件中
            # Args:
            #     md5_for_save (str): 要保存的文件 MD5 值
            with open(get_abs_path(chroma_conf["md5_hex_store"]),"a",encoding="utf-8") as f:
                f.write(md5_for_save+"\n")
        def get_file_documents(file_path:str):
            # 根据文件路径加载文档，自动识别文件类型
            # Args:
            #     file_path (str): 文件绝对路径
            # Returns:
            #     list[Document]: 加载后的文档列表
            if file_path.endswith(".pdf"):
                return pdf_loader(file_path)
            elif file_path.endswith(".txt"):
                return txt_loader(file_path)
            else:
                loggers.error(f"不支持的文件类型:{file_path}")
                return []
        # 获取知识库数据目录的绝对路径
        data_path = get_abs_path(chroma_conf["data_path"])
        loggers.info(f"数据目录：{data_path}")
        loggers.info(f"允许的文件类型：{chroma_conf['allow_knowledge_file_type']}")

        # 获取目录下所有允许的文件类型（PDF 和 TXT）
        allowed_files_path=listdir_with_allowed_type(
            data_path,
            tuple(chroma_conf["allow_knowledge_file_type"])
        )
        # 如果没有找到任何文件，记录错误并返回
        if not allowed_files_path:
            loggers.error(f"未找到任何文件，请检查目录：{data_path}")
            return

        loggers.info(f"找到 {len(allowed_files_path)} 个文件待处理")

        try:
            # 遍历所有文件，逐个加载到向量数据库
            for path in allowed_files_path:
                # 步骤 1: 计算文件 MD5 值
                md5_hex=get_file_md5_hex(path)

                # 步骤 2: 检查是否已加载（通过 MD5 去重）
                if check_md5_hex(md5_hex):
                    loggers.info(f"内容已存在:{path}")
                    continue

                # 步骤 3: 加载文档内容
                documents:list[Document]=get_file_documents(path)
                if not documents:
                    loggers.error(f"无内容:{path}")
                    continue

                # 步骤 4: 文本分块（将长文档切分成合适的小段）
                texts:list[Document]=self.spliter.split_documents(documents)
                if not texts:
                    loggers.error(f"分片后无内容:{path}")
                    continue

                # 步骤 5: 添加到向量数据库（自动计算向量嵌入）
                self.vector_store.add_documents(texts)

                # 步骤 6: 保存 MD5 记录，避免下次重复加载
                save_md5(md5_hex)
                loggers.info(f"内容已添加:{path}")
        except Exception as e:
             loggers.error(f"加载内容出错:{path},错误信息:{e}")

if __name__=="__main__":
    #VectorStoreService().load_document()
    retriever=VectorStoreService().get_retriever()
    result=retriever.invoke("WIFI")
    for r in result:
        print(r.page_content)
        print("-"*20)
