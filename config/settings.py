import os
from typing import Dict

# MongoDB配置
MONGODB_SETTINGS: Dict = {
    "uri": os.getenv(
        "MONGODB_URI",
        "mongodb://你的用户名:你的密码@你的MongoDB地址:端口/admin",
    ),
    "database": os.getenv("MONGODB_DB", "你的数据库名"),
    "collections": {
        "posts": "article",
        "news": "AccNews",
        "news_selections": "NewsSelections",
        "posts_analysis": "PostsAnalysis",
        "events_articles": "EventsArticles",
        "event_comparison": "EventComparison",
        "user_profile": "UserProfile",
        "quotes": "dayk",
        "exponent": "exponent",
    },
}

# LLM配置
LLM_SETTINGS: Dict = {
    "model": os.getenv("LLM_MODEL", "GLM-4-Flash"),  # 使用你可以访问的模型
    "api_key": os.getenv("LLM_API_KEY", "你的LLM_API密钥"),
    "base_url": os.getenv("LLM_BASE_URL", "你的LLM服务地址"),
}

# 数据源映射
SOURCE_TYPE = {
    "cninfo": "巨潮资讯网",
    "xueqiu": "雪球",
    "36kr": "36氪",
    "iresearch": "易观",
    "wind": "万得",
    "gallup": "盖洛普",
    "ccjdd": "东方财经",
    "bloom": "彭博社",
    "reuters": "路透社",
    "qzs": "券商中国",
}

# 线程池配置
PROCESS_POOL = {
    "process_workers": int(os.getenv("PROCESS_MAX_WORKERS", 4)),
    "thread_workers": int(os.getenv("THREAD_MAX_WORKERS", 10)),
}

# 日志配置
LOG_CONFIG = {
    "dir": "logs",
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
}

# 事件整合配置
EVENT_INTEGRATION = {"batch_size": 20}

# 类型映射
TYPE_MAP = {
    "ReadMorning": "早间必读",
    "LogicalReview": "逻辑复盘",
    "Essence": "精华",
}

# Dify配置
DIFY_CONFIG = {
    "dataset_api_key": os.getenv("DIFY_DATASET_API_KEY", "你的Dify数据集API密钥"),
    "dataset_id":os.getenv("DIFY_DATASET_ID","你的Dify数据集ID"),
    "base_url": os.getenv("DIFY_BASE_URL", "你的Dify服务地址"),
    "chat_api_key": os.getenv("DIFY_CHAT_API_KEY", "你的Dify聊天API密钥"),
    "image_api_key": os.getenv("DIFY_IMAGE_API_KEY", "你的Dify图像API密钥"),
}

# 飞书配置
FEISHU_CONFIG = {
    "app_url": os.getenv("FEISHU_APP_URL", "你的飞书Webhook地址"),
}

# OSS配置
OSS_CONFIG = {
    "access_key_id": os.getenv("OSS_ACCESS_KEY_ID", "你的阿里云OSS_AccessKey_ID"),
    "access_key_secret": os.getenv("OSS_ACCESS_KEY_SECRET", "你的阿里云OSS_AccessKey_Secret"),
    "endpoint": os.getenv("OSS_ENDPOINT", "你的OSS服务地址"),
    "bucket_name": os.getenv("OSS_BUCKET_NAME", "你的OSS存储桶名称"),
    "base_path": os.getenv("OSS_BASE_PATH", "images")
}
