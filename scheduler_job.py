import asyncio

from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from tqdm import tqdm

from config.settings import TYPE_MAP, DIFY_CONFIG
from core.article import ArticleService
from core.event import EventProcessor
from core.news import NewsProcessor
from core.posts import PostsProcessor, UserProfileProcessor
from logger import task_logger
from models.database import PostsDB
# from services.dify_document import DifyDatasetAPI  # 已替换为向量服务

# 配置执行器
executors = {
    "default": ThreadPoolExecutor(20),  # 增加线程池大小到20
    "processpool": ProcessPoolExecutor(6),  # 添加进程池支持CPU密集型任务
}

job_defaults = {
    "coalesce": True,  # 错过的任务只运
    "max_instances": 1,  # 同一个任务同时只能有一个实例
    "misfire_grace_time": 3600,  # 任务错过后的补偿时间窗口(秒)
}

# 创建配置后的调度器
scheduler = BackgroundScheduler(
    executors=executors, job_defaults=job_defaults, timezone="Asia/Shanghai"
)


def process_news_job(type: str = "Job"):
    """新闻处理定时任务"""
    try:
        task_logger.info("开始执行新闻处理任务...")
        news_processor = NewsProcessor(type=type)
        asyncio.run(news_processor.extract_news())
        task_logger.info("新闻处理任务完成")
    except Exception as e:
        task_logger.error(f"新闻处理任务失败: {str(e)}", exc_info=True)


def process_posts_job():
    """历史发文处理定时任务"""
    try:
        for type in TYPE_MAP.keys():
            limit = None if type == "Essence" else 100
            task_logger.info(f"开始执行{TYPE_MAP[type]}历史发文处理任务...")
            posts_processor = PostsProcessor(type=type)
            asyncio.run(posts_processor.extract_posts(limit=limit))
            task_logger.info(f"{TYPE_MAP[type]}历史发文处理任务完成")
    except Exception as e:
        task_logger.error(f"历史发文处理任务失败: {str(e)}", exc_info=True)


def user_profile_job():
    """用户画像生成定时任务"""
    try:
        task_logger.info("开始执行用户画像生成任务...")
        user_profile_processor = UserProfileProcessor(type="ReadMorning")
        asyncio.run(user_profile_processor.extract_user_profile())
        task_logger.info("用户画像生成任务完成")
    except Exception as e:
        task_logger.error(f"用户画像生成任务失败: {str(e)}", exc_info=True)


def article_generate_job(type: str = "ReadMorning"):
    """文章生成定时任务"""
    try:
        task_logger.info(f"开始执行{type}文章生成定时任务...")
        # 前置任务：新闻处理
        process_news_job(type)
        task_logger.info("开始执行事件处理任务...")

        event_processor = EventProcessor(type=type)
        asyncio.run(event_processor.generate_events())
        task_logger.info("事件处理任务完成")
        # 生成文章
        for i in range(3):
            article_service = ArticleService(type)
            article = asyncio.run(article_service.generate_article())
            if article:
                # 发送消息
                asyncio.run(article_service.send_feishu_message(article))

        task_logger.info("文章生成定时任务完成")
    except Exception as e:
        task_logger.error(f"文章生成定时任务失败: {str(e)}", exc_info=True)


def update_vector_document_job():
    """更新向量数据库文档定时任务"""
    try:
        from services.vector_service import DocumentManager
        
        task_logger.info("开始执行向量数据库更新任务...")
        
        # 创建文档管理器
        doc_manager = DocumentManager()
        
        # 同步所有类型的帖子到向量数据库
        asyncio.run(doc_manager.sync_posts_to_vector())
        
        # 获取统计信息
        stats = doc_manager.vector_service.get_stats()
        task_logger.info(f"向量数据库统计: {stats}")
        
        task_logger.info("向量数据库更新任务完成")
        
    except Exception as e:
        task_logger.error(f"向量数据库更新任务失败: {str(e)}", exc_info=True)


def init_scheduler():
    """初始化调度器"""
    # 新闻处理（在偶数小时执行：0,2,4,6...）
    scheduler.add_job(
        process_news_job,
        CronTrigger(hour="*/2"),
        id="process_news_job",
        executor="processpool",
    )

    # 历史发文处理（在奇数小时执行：1,3,5,7...）
    scheduler.add_job(
        process_posts_job,
        CronTrigger(hour="1/2"),
        id="process_posts_job",
        executor="processpool",
    )

    # 用户画像生成（每天凌晨00:01）
    scheduler.add_job(
        user_profile_job,
        CronTrigger(hour=0, minute=1),
        id="user_profile_job",
        executor="processpool",
    )

    # 早间必读（早7点）
    scheduler.add_job(
        article_generate_job,
        CronTrigger(hour=7, minute=1),
        id="event_integration_morning",
        executor="processpool",
        args=["ReadMorning"],
    )

    # 逻辑复盘（下午2点）
    scheduler.add_job(
        article_generate_job,
        CronTrigger(hour=14, minute=1),
        id="event_integration_afternoon",
        executor="processpool",
        args=["LogicalReview"],
    )

    # 向量数据库更新（每天上午八点，下午三点）
    scheduler.add_job(
        update_vector_document_job,
        CronTrigger(hour=8, minute=1),
        id="update_vector_document_job_morning",
        executor="processpool",
    )
    scheduler.add_job(
        update_vector_document_job,
        CronTrigger(hour=15, minute=1),
        id="update_vector_document_job_afternoon",
        executor="processpool",
    )


def shutdown_scheduler():
    """关闭调度器以及相关资源"""
    try:
        # 关闭调度器
        if scheduler.running:
            scheduler.shutdown()
            task_logger.info("调度器已关闭")

        # 关闭数据库连接
        from services.mongodb import MongoDBService

        db_service = MongoDBService()
        db_service.close()
        task_logger.info("数据库连接已关闭")
    except Exception as e:
        task_logger.error(f"关闭资源失败: {str(e)}", exc_info=True)


if __name__ == "__main__":
    # init_scheduler()
    # scheduler.start()
    # task_logger.info("调度器已启动")
    #
    # try:
    #     # Keep the script running
    #     while True:
    #         pass
    # except (KeyboardInterrupt, SystemExit):
    #     shutdown_scheduler()
    #     task_logger.info("调度器已关闭")
    article_generate_job()
