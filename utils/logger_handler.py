import logging
import os
from utils.path_tool import get_abs_path
from datetime import datetime

#日志保存根目录
LOG_ROOT=get_abs_path("logs")

#确保目录存在
os.makedirs(LOG_ROOT,exist_ok=True)

#日志格式
# ... existing code ...
DEFAULT_LOG_FORMAT=logging.Formatter(
    fmt="%(asctime)s %(levelname)s [%(name)s] %(filename)s:%(lineno)d %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
# ... existing code ...


def get_logger(
        name:str="agent",
        console_level:int=logging.INFO,
        file_level:int=logging.DEBUG,
        log_file:str=None,
        )->logging.Logger:
    logger=logging.getLogger(name)
    logger.setLevel(file_level)
    #避免重复添加
    if logger.handlers:
        return logger

    #控制台
    console_handler=logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)
    logger.addHandler(console_handler)

    #文件
    if not log_file:
        log_file=os.path.join(LOG_ROOT,f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log")

    file_handler=logging.FileHandler(log_file,encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)
    logger.addHandler(file_handler)

    return logger

#快捷获取
loggers=get_logger()

if __name__=="__main__":
    loggers.info("hello world")
    loggers.error("error")
    loggers.warning("warning")
    loggers.debug("debug")