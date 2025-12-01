import hashlib
from datetime import datetime
from typing import Dict, List

from pymongo import DESCENDING

from config.settings import MONGODB_SETTINGS
from logger import task_logger
from services.mongodb import MongoDBService


class BaseDBModel:
    """数据库基础模型类"""

    _mongodb_service = None

    def __init__(self):
        if not BaseDBModel._mongodb_service:
            BaseDBModel._mongodb_service = MongoDBService()
        self.mongodb = BaseDBModel._mongodb_service

    @classmethod
    def close_connection(cls):
        """
        安全关闭MongoDB连接
        应在应用退出前调用此方法
        """
        if cls._mongodb_service:
            try:
                cls._mongodb_service.close()
                cls._mongodb_service = None
            except Exception:
                pass


class NewsDB(BaseDBModel):
    """新闻数据库"""

    def __init__(self):
        super().__init__()
        self.NewsDB = MONGODB_SETTINGS["collections"]["news"]
        self.NewsSelectionDB = MONGODB_SETTINGS["collections"]["news_selections"]

    async def get_news_by_id(self, news_id: str, limit: int = 1) -> Dict:
        """根据新闻id获取新闻"""
        query = {"md5": news_id}
        projection = {
            "_id": 0,
        }
        sorted_field = "timestamp"

        news = self.mongodb.fetch_data(
            collection_name=self.NewsDB,
            query=query,
            projection=projection,
            sort_field=sorted_field,
            limit=limit,
        )

        return news[0] if news else None

    async def get_news_by_time(
        self,
        start_time: int,
        end_time: int,
        date_field: str = "timestamp",
        sort_field: str = "timestamp",
        sort_order: int = -1,
        limit: int = None,
    ) -> List[Dict]:
        """
        获取指定时间范围内的新闻
        :param start_time: 开始时间戳（秒）
        :param end_time: 结束时间戳（秒）
        :param date_field: 日期字段，默认为timestamp
        :param sort_field: 排序字段，默认为timestamp
        :param sort_order: 排序方式（-1降序/1升序），默认降序
        :param limit: 返回结果数量限制，默认不限制
        :return: 新闻列表
        """
        try:
            query = {
                date_field: {"$gte": start_time, "$lte": end_time},
            }
            projection = {"_id": 0}

            news_list = self.mongodb.fetch_data(
                collection_name=self.NewsDB,
                query=query,
                projection=projection,
                sort_field=sort_field,
                sort_order=sort_order,
                limit=limit,
            )

            return news_list
        except Exception as e:
            task_logger.info(f"❌ 获取时间范围新闻错误: {e}")
            return []

    async def get_news_selection_data(
        self,
        start_time: int,
        end_time: int,
        date_field: str = "date",
        sort_field: str = "date",
        sort_order: int = -1,
        limit: int = None,
    ) -> List[Dict]:
        """获取新闻选择数据"""
        try:
            query = {
                date_field: {"$gte": start_time, "$lte": end_time},
            }
            projection = {"_id": 0}
            news_selection_data = self.mongodb.fetch_data(
                collection_name=self.NewsSelectionDB,
                query=query,
                projection=projection,
                sort_field=sort_field,
                sort_order=sort_order,
                limit=limit,
            )
            return news_selection_data
        except Exception as e:
            task_logger.info(f"❌ 获取新闻选择数据错误: {e}")
            return []

    async def save_news_result(self, news_data: dict) -> bool:
        """保存新闻数据"""
        # 构建保存数据
        selection_data = {
            "id": news_data.get("id", None),
            "evaluations_score": news_data.get("evaluations_score", 0),
            "topic_result": news_data.get("topic_result", None),
            "topic_score": news_data.get("topic_score", 0),
            "logic_result": news_data.get("logic_result", None),
            "logic_score": news_data.get("logic_score", 0),
            "date": news_data.get("date", None),
        }

        # 插入数据
        result = self.mongodb.insert_document(
            collection_name=self.NewsSelectionDB, document=selection_data
        )

        return result

    async def update_news_field(self, id: str, data: dict) -> bool:
        """更新新闻字段"""

        # 更新新闻处理状态
        query = {"id": id}
        update = {"$set": data}
        result = self.mongodb.update_document(
            collection_name=self.NewsSelectionDB, query=query, update=update
        )

        return result


class EventsArticleDB(BaseDBModel):
    """事件文章数据库"""

    def __init__(self):
        super().__init__()
        self.EventsArticleDB = MONGODB_SETTINGS["collections"]["events_articles"]
        self.EventComparisonDB = MONGODB_SETTINGS["collections"]["event_comparison"]

    async def get_events_articles(self, type: str, limit: int = 10) -> List[Dict]:
        """获取事件文章"""
        query = {"type": type}
        projection = {
            "_id": 0,
            "id": 1,
            "events": 1,
            "content": 1,
            "type": 1,
            "create_time": 1,
        }
        sorted_field = "create_time"
        events_articles = self.mongodb.fetch_data(
            collection_name=self.EventsArticleDB,
            query=query,
            projection=projection,
            sort_field=sorted_field,
            limit=limit,
        )

        return events_articles

    async def get_events(self, type: str) -> List[Dict]:
        """获取事件"""
        events_articles = await self.get_events_articles(type)
        if not events_articles:
            return []
        return events_articles[0].get("events", [])

    async def get_article(self, type: str) -> Dict:
        """获取文章"""
        events_articles = await self.get_events_articles(type)
        if not events_articles:
            return {}
        return events_articles[0].get("content", "")

    async def insert_events(self, events: List[Dict], type: str) -> bool:
        """插入事件"""
        id = hashlib.md5(
            (type + datetime.now().strftime("%Y-%m-%d %H:%M:%S")).encode()
        ).hexdigest()
        events_data = {
            "id": id,
            "events": events,
            "content": "",
            "type": type,
            "create_time": int(datetime.now().timestamp()),
        }
        result = self.mongodb.insert_document(
            collection_name=self.EventsArticleDB,
            document=events_data,
        )
        return result

    async def update_article(self, id: str, article: str) -> bool:
        """更新文章"""
        query = {"id": id}
        update = {"$set": {"content": article}}
        result = self.mongodb.update_document(
            collection_name=self.EventsArticleDB,
            query=query,
            update=update,
        )
        return result

    async def get_event_comparison(self, id_list: List[str]) -> List[Dict]:
        """获取事件对比"""
        events_comparison = self.mongodb.batch_fetch_by_ids(
            collection_name=self.EventComparisonDB,
            id_list=id_list,
        )
        return events_comparison

    async def save_event_comparison(self, event_comparison: Dict) -> bool:
        """保存事件对比"""
        result = self.mongodb.insert_document(
            collection_name=self.EventComparisonDB,
            document=event_comparison,
        )
        return result


class UserProfileDB(BaseDBModel):
    """用户画像数据库"""

    def __init__(self):
        super().__init__()
        self.UserProfileDB = MONGODB_SETTINGS["collections"]["user_profile"]

    async def get_writing_style(self) -> Dict:
        """获取用户写作风格"""
        projection = {
            "_id": 0,
            "writing_style": 1,
        }
        sorted_field = "create_time"
        user_profile = self.mongodb.fetch_data(
            collection_name=self.UserProfileDB,
            projection=projection,
            sort_field=sorted_field,
        )

        return user_profile[0].get("writing_style", {}) if user_profile else None

    async def get_topics(self) -> Dict:
        """获取用户主题"""
        projection = {
            "_id": 0,
            "topics": 1,
        }
        sorted_field = "create_time"
        user_profile = self.mongodb.fetch_data(
            collection_name=self.UserProfileDB,
            projection=projection,
            sort_field=sorted_field,
        )

        return user_profile[0].get("topics", {}) if user_profile else None

    async def get_topic_profile(self) -> Dict:
        """获取用户主题市场画像"""
        projection = {
            "_id": 0,
            "topic_profile": 1,
        }
        sorted_field = "create_time"
        user_profile = self.mongodb.fetch_data(
            collection_name=self.UserProfileDB,
            projection=projection,
            sort_field=sorted_field,
        )

        return user_profile[0].get("topic_profile", {}) if user_profile else None

    async def get_logic_profile(self) -> Dict:
        """获取用户逻辑画像"""
        projection = {
            "_id": 0,
            "logic_profile": 1,
        }
        sorted_field = "create_time"
        user_profile = self.mongodb.fetch_data(
            collection_name=self.UserProfileDB,
            projection=projection,
            sort_field=sorted_field,
        )

        return user_profile[0].get("logic_profile", {}) if user_profile else None

    async def save_user_profile(self, profile_data: Dict) -> bool:
        """保存用户画像"""
        # 生成唯一ID
        id = hashlib.md5(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S").encode()
        ).hexdigest()

        # 构建保存数据
        profile_data["id"] = id
        profile_data["create_time"] = int(datetime.now().timestamp())

        # 插入数据
        result = self.mongodb.insert_document(
            collection_name=self.UserProfileDB, document=profile_data
        )

        return result

    async def update_user_profile(self, id: str, field: str, value: str) -> bool:
        """更新用户画像"""
        query = {"id": id}
        update = {
            "$set": {field: value, "create_time": int(datetime.now().timestamp())}
        }
        result = self.mongodb.update_document(
            collection_name=self.UserProfileDB,
            query=query,
            update=update,
        )

        return result


class PostsDB(BaseDBModel):
    """历史发文数据库"""

    def __init__(self):
        super().__init__()
        self.PostsDB = MONGODB_SETTINGS["collections"]["posts"]
        self.PostsAnalysisDB = MONGODB_SETTINGS["collections"]["posts_analysis"]

    async def get_posts(self, type: str, limit: int = 20) -> List[Dict]:
        """获取历史发文"""
        query = {"type": type}
        projection = {"_id": 0, "mes": 1, "date": 1, "type": 1, "md5": 1}
        sorted_field = "date"
        posts = self.mongodb.fetch_data(
            collection_name=self.PostsDB,
            query=query,
            projection=projection,
            sort_field=sorted_field,
            sort_order=DESCENDING,
            limit=limit,
        )

        return posts

    async def get_posts_by_ids(self, ids: List[str]) -> List[Dict]:
        """根据id获取历史发文"""
        posts = self.mongodb.batch_fetch_by_ids(
            collection_name=self.PostsDB,
            ids_field="md5",
            id_list=ids,
        )
        return posts

    async def save_market_analysis(self, analysis_data: Dict) -> bool:
        """保存市场分析结果 - 重定向到save_posts_analysis方法"""
        # 由于MarketAnalysisDB已合并到PostsAnalysisDB，重定向到新方法
        return self.save_posts_analysis(analysis_data)

    async def get_latest_market_analysis(self) -> Dict:
        """获取最新的市场分析结果 - 重定向到get_latest_posts_analysis方法"""
        # 由于MarketAnalysisDB已合并到PostsAnalysisDB，重定向到新方法
        return await self.get_latest_posts_analysis()

    async def save_posts_analysis(self, analysis_data: Dict) -> bool:
        """保存历史发文分析结果"""
        if not analysis_data:
            return False

        if "id" not in analysis_data:
            # 生成唯一ID
            id = hashlib.md5(
                f"posts_analysis_{datetime.now().strftime('%Y-%m-%d')}".encode()
            ).hexdigest()
            analysis_data["id"] = id

        # 插入数据
        result = self.mongodb.insert_document(
            collection_name=self.PostsAnalysisDB, document=analysis_data
        )

        return result

    async def update_posts_analysis(self, id: str, data: dict) -> bool:
        """更新历史发文分析结果"""
        query = {"id": id}
        update = {"$set": data}
        result = self.mongodb.update_document(
            collection_name=self.PostsAnalysisDB,
            query=query,
            update=update,
        )

        return result

    async def get_posts_analysis(self, type: str, limit: int = 10, skip: int = 0) -> List[Dict]:
        """获取历史发文分析结果"""
        projection = {"_id": 0}
        query = {"type": type}
        sorted_field = "date"

        analysis_list = self.mongodb.fetch_data(
            collection_name=self.PostsAnalysisDB,
            query=query,
            projection=projection,
            sort_field=sorted_field,
            sort_order=DESCENDING,
            skip=skip,
            limit=limit,
        )

        return analysis_list


class MarketDB(BaseDBModel):
    """市场数据库"""

    def __init__(self):
        super().__init__()
        self.quotesDB = MONGODB_SETTINGS["collections"]["quotes"]
        self.exponentDB = MONGODB_SETTINGS["collections"]["exponent"]

    async def get_quotes(self) -> List[Dict]:
        """获取上证所数据"""
        projection = {
            "_id": 1,
            "k": 1,
            "day": 1,
        }
        sort_field = "day"
        sse_list = self.mongodb.fetch_data(
            collection_name=self.quotesDB,
            projection=projection,
            sort_field=sort_field,
        )

        k = sse_list[0].get("k", {})
        return k

    async def get_exponent(self) -> List[Dict]:
        """获取指数数据"""
        exponents_types = ["000001.SH", "N225.GI", "IXIC.GI"]
        exponents = {}
        for exponents_type in exponents_types:
            query = {"type": exponents_type}
            projection = {
                "_id": 0,
                "open": 1,
                "close": 1,
                "changeRatio": 1,
                "time": 1,
                "type": 1,
            }
            sort_field = "time"
            exponent = self.mongodb.fetch_data(
                collection_name=self.exponentDB,
                query=query,
                projection=projection,
                sort_field=sort_field,
            )
            exponents[exponents_type] = {
                "open": exponent[0]["open"],
                "close": exponent[0]["close"],
                "changeRatio": round(exponent[0]["changeRatio"], 2),
            }

        return exponents
