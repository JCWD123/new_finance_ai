import logging
import os
from logging.handlers import TimedRotatingFileHandler

from config.settings import LOG_CONFIG

# 日志配置
LOG_DIR = LOG_CONFIG.get("dir")
LOG_LEVEL = LOG_CONFIG.get("level")
LOG_FORMAT = LOG_CONFIG.get("format")


def setup_logger(name, log_file):
    """设置日志记录器"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(LOG_LEVEL)

    # 文件处理器
    file_handler = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, log_file), when="midnight", interval=1, backupCount=30
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 创建不同的日志记录器
api_logger = setup_logger("api", "api.log")
task_logger = setup_logger("task", "task.log")
token_logger = setup_logger("token", "token.log")
