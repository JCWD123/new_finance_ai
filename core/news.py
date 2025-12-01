import json
from datetime import datetime
from typing import List, Dict, Tuple

import pandas as pd

from logger import task_logger
from models.database import EventsArticleDB, NewsDB, MarketDB, UserProfileDB
from prompt.news import *
from prompt.util import OutputFormatConstraint
from services.llm import LLMService
from utils.task_utils import TaskManager
from utils.time_utils import calculate_base_time
from utils.tools import remove_sensitive_information


class NewsProcessor:
    """新闻处理核心逻辑"""

    def __init__(self, type: str = "ReadMorning"):
        self.type = type
        # 不再直接创建MongoDBService实例，而是使用数据库模型类
        self.events_db = EventsArticleDB()
        self.news_db = NewsDB()
        self.market_db = MarketDB()
        self.user_db = UserProfileDB()
        # 使用events_db实例中的mongodb连接
        self.mongodb = self.events_db.mongodb
        self.llm = LLMService()
        self.task_mgr = TaskManager()
        self.now = datetime.now()
        self.end_time, self.start_time = calculate_base_time(self.now, type=self.type)

    async def get_filtered_news(self, news_list: List[Dict]) -> List[Dict]:
        """过滤新闻"""
        news_df = pd.DataFrame(news_list)
        ids = news_df["md5"].tolist()
        news_selection_list = self.mongodb.batch_fetch_by_ids(
            collection_name=self.news_db.NewsSelectionDB, id_list=ids
        )
        if news_selection_list:
            news_selection_df = pd.DataFrame(news_selection_list)
            ids = news_selection_df[
                (news_selection_df["evaluations_score"] != 0)
                & (news_selection_df["topic_result"].notna())
                & (news_selection_df["logic_result"].notna())
            ]["id"].tolist()
            news_list = [news for news in news_list if news["md5"] not in ids]

        return news_list

    async def extract_news(self, news_list: List[Dict] = []) -> List[Dict]:
        """处理新闻"""
        try:
            task_logger.info("开始执行新闻处理...")
            # 获取新闻
            if news_list == []:
                news_list = await self.news_db.get_news_by_time(
                    self.start_time, self.end_time
                )
            if not news_list:
                task_logger.info("没有找到新的新闻，跳过本次处理")
                return []

            # 过滤掉已处理的新闻
            news_list = await self.get_filtered_news(news_list)
            task_logger.info(f"找到{len(news_list)}条未处理的新闻")

            results = await self.task_mgr.process_tasks(
                self._process_single_news, news_list
            )

            # 过滤掉None结果
            results = [r for r in results if r]

            task_logger.info(f"成功处理{len(results)}条新闻")
            task_logger.info("新闻处理完成")
            return results
        except Exception as e:
            task_logger.error(f"新闻处理失败: {str(e)}", exc_info=True)
            return []

    async def _process_single_news(self, news: Dict) -> Dict:
        """处理单条新闻"""
        try:
            news_data = {
                "id": news.get("md5", ""),
                "mes": remove_sensitive_information(news.get("mes", "")),
                "date": datetime.fromtimestamp(
                    news.get("timestamp", int(datetime.now().timestamp()))
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "source": news.get("from", ""),
            }
            # 提取新闻要点
            task_logger.info(f"开始提取新闻要点: {news_data.get('id')}")
            points_result = await self._extract_single_news_points(news_data)
            if not points_result:
                task_logger.error(f"无法提取新闻要点: {news_data.get('id')}")
            task_logger.info(f"新闻要点提取完成: {news_data.get('id')}")
            # 主题分析
            task_logger.info(f"开始分析新闻主题: {news_data.get('id')}")
            topics = await self._get_topics()
            user_interest = await self._get_user_interest()
            topic_result = await self._analyze_single_news_topic(
                news_data, topics, user_interest
            )
            if not topic_result:
                task_logger.error(f"无法分析新闻主题: {news_data.get('id')}")
            task_logger.info(f"新闻主题分析完成: {news_data.get('id')}")
            # 逻辑过滤
            task_logger.info(f"开始逻辑过滤新闻: {news_data.get('id')}")
            user_logic_map = await self._get_user_logic_map()
            logic_result = await self._filter_news_by_logic(news_data, user_logic_map)
            if not logic_result:
                task_logger.error(f"无法逻辑过滤新闻: {news_data.get('id')}")
            task_logger.info(f"逻辑过滤新闻完成: {news_data.get('id')}")
            # 保存新闻结果
            news_result = {
                "id": news_data.get("id", ""),
                "evaluations_score": points_result.get("evaluations_score", 0),
                "topic_result": topic_result.get("topic_result", None),
                "topic_score": topic_result.get("topic_score", 0),
                "logic_result": logic_result.get("logic_result", None),
                "logic_score": logic_result.get("logic_score", 0),
                "date": news.get("timestamp", int(datetime.now().timestamp())),
            }

            if not self.mongodb.check_id_exists(
                collection_name=self.news_db.NewsSelectionDB, id=news_data.get("id")
            ):
                await self.news_db.save_news_result(news_result)
            else:
                data = {
                    "evaluations_score": news_result.get("evaluations_score", 0),
                    "topic_result": news_result.get("topic_result", None),
                    "topic_score": news_result.get("topic_score", 0),
                    "logic_result": news_result.get("logic_result", None),
                    "logic_score": news_result.get("logic_score", 0),
                }
                await self.news_db.update_news_field(id=news_data.get("id"), data=data)
            return points_result, topic_result, logic_result
        except Exception as e:
            task_logger.error(f"处理单条新闻失败: {str(e)}", exc_info=True)
            return None

    async def _extract_single_news_points(self, news: Dict) -> Dict:
        """处理单条新闻要点"""
        try:
            news_str = json.dumps(news, ensure_ascii=False)
            full_prompt = NewsSelcetionAndPointsExtractPrompt.format(
                news=news_str, OutputFormatConstraint=OutputFormatConstraint
            )
            messages = [
                {
                    "role": "system",
                    "content": NewsSelcetionAndPointsExtractSystemPrompt,
                },
                {"role": "user", "content": full_prompt},
            ]

            think_response, json_response = self.llm.call_llm(messages=messages)

            if not json_response:
                task_logger.error(f"无法解析新闻要点: {news.get('id')}")
                return None

            # 处理返回的结果
            result = {
                "id": news.get("id", ""),
                "evaluations_score": json_response.get("all_score", 0),
            }

            return result
        except Exception as e:
            task_logger.error(f"处理单条新闻失败: {str(e)}", exc_info=True)
            return None

    async def _analyze_single_news_topic(
        self, news: Dict, topics: Dict, user_interest: Dict
    ) -> Dict:
        """单条新闻主题分析"""
        try:
            news_str = json.dumps(news, ensure_ascii=False)
            full_prompt = NewsSelcetionTopicPrompt.format(
                news=news_str,
                topics=topics,
                user_interest=user_interest,
                OutputFormatConstraint=OutputFormatConstraint,
            )
            messages = [
                {"role": "system", "content": NewsSelcetionTopicSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            think_response, json_response = self.llm.call_llm(messages=messages)

            if not json_response:
                task_logger.error(f"无法分析主题: {news.get('id')}")
                return None

            # 处理返回的结果
            result = {
                "id": news.get("id", ""),
                "topic_result": json_response.get("screening_result", {}).get(
                    "result", None
                ),
                "topic_score": json_response.get("screening_result", {}).get(
                    "score", 0
                ),
            }

            return result
        except Exception as e:
            task_logger.error(f"主题分析失败: {str(e)}", exc_info=True)
            return None

    async def _filter_news_by_logic(self, news: Dict, user_logic_map: Dict) -> Dict:
        """按逻辑过滤新闻"""
        try:
            news_str = json.dumps(news, ensure_ascii=False)
            full_prompt = FilterLogicalNewsPrompt.format(
                news_data=news_str,
                filter_logic_map=user_logic_map,
                OutputFormatConstraint=OutputFormatConstraint,
            )
            messages = [
                {"role": "system", "content": FilterLogicalNewsSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            think_response, json_response = self.llm.call_llm(messages=messages)

            if not json_response:
                task_logger.error(f"无法过滤新闻: {news.get('id')}")
                return None

            # 处理返回的结果
            result = {
                "id": news.get("id", ""),
                "logic_result": json_response.get("result", None),
                "logic_score": json_response.get("score", 0),
            }

            return result
        except Exception as e:
            task_logger.error(f"逻辑过滤新闻失败: {str(e)}", exc_info=True)
            return None

    async def _get_topics(self) -> Dict:
        """获取主题配置"""
        try:
            topics = await self.user_db.get_topics()
            if topics:
                return topics
            else:
                return {}
        except Exception as e:
            task_logger.error(f"获取主题配置失败: {str(e)}", exc_info=True)
            return {}

    async def _get_user_interest(self) -> Dict:
        """获取用户兴趣配置"""
        try:
            # 首先尝试从数据库获取
            topic_profile = await self.user_db.get_topic_profile()
            if topic_profile:
                return topic_profile
            else:
                return {}
        except Exception as e:
            task_logger.error(f"获取用户兴趣配置失败: {str(e)}", exc_info=True)
            return {}

    async def _get_user_logic_map(self) -> Dict:
        """获取用户逻辑画像"""
        try:
            # 首先尝试从数据库获取
            logic_profile = await self.user_db.get_logic_profile()
            if logic_profile:
                return logic_profile
            else:
                return {}
        except Exception as e:
            task_logger.error(f"获取用户逻辑画像失败: {str(e)}", exc_info=True)
            return {}

    async def get_article_param(self) -> Tuple:
        """获取文章参数"""
        try:
            # 获取事件
            events_articles = await self.events_db.get_events_articles(self.type)
            if not events_articles:
                return [], None, 0

            events = events_articles[0].get("events", [])
            article = events_articles[0].get("content", "")
            create_time = events_articles[0].get("create_time", 0)

            return events, article, create_time
        except Exception as e:
            task_logger.error(f"获取文章参数失败: {str(e)}", exc_info=True)
            return [], None, 0


class NewsService(NewsProcessor):
    """新闻服务类"""

    def __init__(self, type: str = "ReadMorning"):
        super().__init__(type)
        self.today_date = datetime.now().date()

    async def get_dashboard_news(self, type: str = None) -> List[Dict]:
        """获取资讯数据"""
        try:
            if type:
                self.type = type
            events, _, _ = await self.get_article_param()
            return events
        except Exception as e:
            task_logger.error(f"获取资讯数据失败: {str(e)}")
            return []

    async def get_news_detail(self, news_id: str) -> Dict:
        """获取新闻详情"""
        try:
            news = await self.news_db.get_news_by_id(news_id)
            if news:
                return {
                    "id": news.get("md5", ""),
                    "title": news.get("title", ""),
                    "content": news.get("mes", ""),
                    "link": news.get("link", ""),
                    "type": news.get("type", ""),
                    "from": news.get("from", ""),
                }
            return {}
        except Exception as e:
            task_logger.error(f"获取新闻详情失败: {str(e)}")
            return {}

    async def get_market_data(self) -> Dict:
        """获取市场数据"""
        try:
            quotes = await self.market_db.get_quotes()
            exponent = await self.market_db.get_exponent()
            if quotes and exponent:
                return {"kLineData": quotes, "exponent": exponent}
        except Exception as e:
            task_logger.error(f"获取市场数据失败: {str(e)}")

        return {}
