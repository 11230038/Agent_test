import os,hashlib
from utils.logger_handler import loggers
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader,TextLoader

#获取文件的md5
def get_file_md5_hex(file_path:str):
    if not os.path.exists(file_path):
        loggers.error(f"文件不存在:{file_path}")
        return None
    if not os.path.isfile(file_path):
        loggers.error(f"不是文件:{file_path}")
        return None

    md5_obj=hashlib.md5()
    #分片
    chunk_size=4096
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)
        return md5_obj.hexdigest()
    except Exception as e:
        loggers.error(f"获取文件md5出错:{file_path},错误信息:{e}")
        return None

#递归扫描文件夹，返回文件路径列表（每项包含路径和分类）
def listdir_with_allowed_type(path:str,allowed_types:tuple,default_category:str="扫地机器人客服"):
    results = []
    if not os.path.isdir(path):
        loggers.error(f"目录不存在:{path}")
        return tuple(results)
    for root, dirs, files in os.walk(path):
        for file in files:
            if os.path.splitext(file)[1] in allowed_types:
                file_path = os.path.join(root, file)
                # 根据子目录确定分类
                rel_dir = os.path.relpath(root, path)
                category = rel_dir if rel_dir != "." else default_category
                results.append((file_path, category))
    return tuple(results)

#读取pdf文件
def pdf_loader(file_path:str,passwd=None)->list[Document]:
    return PyPDFLoader(file_path,passwd).load()

#读取txt文件
def txt_loader(file_path:str)->list[Document]:
    encodings = ['utf-8', 'gbk', 'gb18030']
    for encoding in encodings:
        try:
           return TextLoader(file_path, encoding=encoding).load()
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"无法解码文件：{file_path}，尝试的编码：{encodings}")

