import json
from datetime import datetime
from typing import List, Dict, Tuple

import pandas as pd

from config.settings import EVENT_INTEGRATION
from logger import task_logger
from models.database import EventsArticleDB, NewsDB
from prompt.event import *
from prompt.util import OutputFormatConstraint
from services.llm import LLMService
from utils.task_utils import TaskManager
from utils.time_utils import calculate_base_time
from utils.tools import remove_sensitive_information


class EventProcessor:
    """事件处理核心逻辑"""

    def __init__(self, type: str = "ReadMorning"):
        self.type = type
        self.events_db = EventsArticleDB()
        self.news_db = NewsDB()
        # 使用events_db实例中的mongodb连接
        self.mongodb = self.events_db.mongodb
        self.llm = LLMService()
        self.task_mgr = TaskManager()
        self.now = datetime.now()
        self.end_time, self.start_time = calculate_base_time(
            now=self.now, type=self.type
        )

    async def event_compare(self, event1: dict, event2: dict) -> Tuple:
        """
        执行事件对比
        :param event1: 第一个事件数据
        :param event2: 第二个事件数据
        :return: 思考过程和JSON格式的对比结果
        """
        task_logger.info("正在执行事件对比......")

        full_prompt = EventComparisonPrompt.format(
            article1=event1,
            article2=event2,
            OutputFormatConstraint=OutputFormatConstraint,
        )
        messages = [
            {"role": "system", "content": EventComparisonSystemPrompt},
            {"role": "user", "content": full_prompt},
        ]

        think_response, json_response = self.llm.call_llm(messages=messages)

        if not json_response:
            task_logger.error("事件对比失败，未能获取有效结果")
            return {}

        return json_response

    async def _events_integration_extract(self, events: List[Dict]) -> List[Dict]:
        """
        事件整合提取
        :param events: 事件列表
        :return: 事件整合列表
        """
        task_logger.info("开始执行事件整合提取...")
        events_str = json.dumps(events, ensure_ascii=False)
        full_prompt = EventIntegrationPrompt.format(
            events=events_str, OutputFormatConstraint=OutputFormatConstraint
        )
        messages = [
            {"role": "system", "content": EventIntegrationSystemPrompt},
            {"role": "user", "content": full_prompt},
        ]

        think_response, json_response = self.llm.call_llm(messages=messages)

        if not json_response:
            task_logger.error("事件整合提取失败，未能获取有效结果")
            return []

        return json_response

    async def get_highest_scored_event(self, group: dict, events: List[Dict]) -> Dict:
        """获取组内评分最高的代表性事件
        Args:
            group: 事件组，包含 event_ids 列表
        Returns:
            dict: 评分最高的事件，如果组内没有有效事件则返回 {}
        """
        news_map = {event["id"]: event for event in events}
        try:
            # 获取组内所有有效事件
            group_news = [
                news_map[event_id]
                for event_id in group["event_ids"]
                if event_id in news_map
            ]

            if not group_news:
                task_logger.warning(f"事件组 {group['event_ids']} 中没有找到有效事件")
                return {}

            # 根据评分排序并返回最高分事件
            sorted_news = sorted(
                group_news,
                key=lambda x: float(x.get("score", 0)),  # 使用 get 避免 KeyError
                reverse=True,
            )

            highest_scored = {
                "id": sorted_news[0]["id"],
                "date": datetime.fromtimestamp(sorted_news[0]["date"]).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "mes": sorted_news[0]["mes"],
            }
            # scheduler_logger.info(
            #     f"选择评分为 {sorted_news[0].get('score')} 的事件作为代表"
            # )
            return highest_scored

        except Exception as e:
            task_logger.error(f"获取代表性事件时发生错误: {str(e)}")
            return {}

    async def process_events_integration_result(
        self, events: List[Dict], events_integration_result: list, events_result: list
    ) -> List[Dict]:
        """
        处理事件整合结果
        """
        short_events_result = []
        if events_result:
            for group in events_integration_result:
                event = await self.get_highest_scored_event(group, events)
                id = event["id"]
                num = 0
                for index, ev in enumerate(events_result):
                    if id in ev["event_ids"]:
                        events_result[index]["event_ids"].extend(group["event_ids"])
                        num += 1
                if num == 0:
                    short_events_result.append(group)
            events_result.extend(short_events_result)
        else:
            events_result = events_integration_result
        return events_result

    async def events_integration_extract(self, events: List[Dict]) -> List[Dict]:
        """
        事件整合
        :param events: 事件列表，若为None则从数据库获取
        :return: 事件整合列表
        """
        try:
            task_logger.info("开始执行事件整合...")

            events_sanitized = [
                {
                    "id": event["id"],
                    "mes": event["mes"],
                    "date": datetime.fromtimestamp(event["date"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
                for event in events
            ]
            events_integration_result = []
            while len(events_sanitized) > 30:
                # 调用LLM进行事件整合
                events_integration = await self.task_mgr.process_tasks(
                    self._events_integration_extract,
                    [
                        events[i : i + EVENT_INTEGRATION["batch_size"]]
                        for i in range(
                            0, len(events_sanitized), EVENT_INTEGRATION["batch_size"]
                        )
                    ],
                    use_processes=False,
                )
                events_integration = [
                    {
                        "event_summary": item["event_summary"],
                        "event_ids": item["event_id"],
                    }
                    for sublist in events_integration
                    for item in sublist
                ]
                events_integration_result.append(events_integration)
                events_sanitized = [
                    await self.get_highest_scored_event(group, events)
                    for group in events_integration
                ]
            events_result = []
            for eir in reversed(events_integration_result):
                events_result += await self.process_events_integration_result(
                    events, eir, events_result
                )
            if not events_result and len(events) < 30:
                events_result = [{"event_ids": [event["id"]],"event_summary": ""} for event in events]
            events_df = pd.DataFrame(events)
            result = []
            for er in events_result:
                highest_event = await self.get_highest_scored_event(er, events)
                er["event_id"] = highest_event["id"]
                title = events_df[events_df["id"] == highest_event["id"]][
                    "title"
                ].tolist()[0]
                score = events_df[events_df["id"] == highest_event["id"]][
                    "score"
                ].tolist()[0]
                er["title"] = title
                er["content"] = highest_event["mes"]
                er["score"] = score
                df = events_df[events_df["id"].isin(er["event_ids"])]
                er["mes"] = df["mes"].tolist()
                er["links"] = df["link"].tolist()
                er["titles"] = df["title"].tolist()
                er["from"] = df["from"].tolist()
                er["date"] = datetime.fromtimestamp(df["date"].max()).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                result.append(er)

            # 返回整合结果
            task_logger.info("事件整合完成")
            return result

        except Exception as e:
            task_logger.error(f"事件整合失败: {str(e)}", exc_info=True)
            return []

    async def _same_event_integration_extract(self, events: dict) -> Dict:
        """
        同一事件整合提炼
        """
        task_logger.info(f"开始执行 {events['id']} 同一事件整合提炼...")
        id = events["id"]
        mes = events["mes"]
        events_str = json.dumps(mes, ensure_ascii=False)
        full_prompt = SameEventIntegrationPrompt.format(
            events=events_str, OutputFormatConstraint=OutputFormatConstraint
        )
        messages = [
            {"role": "system", "content": SameEventIntegrationSystemPrompt},
            {"role": "user", "content": full_prompt},
        ]

        think_response, json_response = self.llm.call_llm(messages=messages)

        if not json_response:
            task_logger.error(f"{events['id']} 事件整合提炼失败，未能获取有效结果")
            return {}

        # 返回整合结果
        return {"id": id, "event_summary": json_response["event_summary"]}

    async def same_event_integration(self, events: List[Dict]) -> List:
        """
        对同一事件的多篇报道进行整合提炼
        :param events: 同一事件的多篇报道
        :return: 整合后的事件
        """
        try:
            task_logger.info("开始执行同一事件整合提炼...")

            events_sanitized = [
                {"id": event["event_id"], "mes": event["mes"]} for event in events
            ]

            # 调用LLM进行事件整合
            same_event_integration = await self.task_mgr.process_tasks(
                self._same_event_integration_extract,
                events_sanitized,
                use_processes=False,
            )

            result = []
            for event in events:
                event["event_summary"] = [
                    key["event_summary"]
                    for key in same_event_integration
                    if key["id"] == event["event_id"]
                ][0]
                result.append(event)
            task_logger.info("同一事件整合提炼完成")
            return result
        except Exception as e:
            task_logger.error(f"事件整合提炼失败: {str(e)}", exc_info=True)
            return {}

    async def get_filtered_events(self, events: List[Dict]) -> List[Dict]:
        """
        过滤新闻事件
        """
        events_df = pd.DataFrame(events)
        try:
            events_df = events_df[
                (events_df["topic_result"] == True)
                & (events_df["logic_result"] == True)
            ]
        except KeyError as e:
            pass
        events_df["score"] = (
            events_df["evaluations_score"] * 0.2
            + events_df["topic_score"] * 0.5
            + events_df["logic_score"] * 0.3
        )
        events_df = events_df[["id", "score", "date"]]
        events_df = events_df.sort_values(by="score", ascending=False)
        events_df.reset_index(drop=True, inplace=True)
        events_ids = events_df["id"].tolist()
        news_list = self.mongodb.batch_fetch_by_ids(
            collection_name=self.news_db.NewsDB,
            id_list=events_ids,
            ids_field="md5",
            projection={"_id": 0, "md5": 1, "mes": 1, "title": 1, "link": 1, "from": 1},
        )
        news_df = pd.DataFrame(news_list)
        news_df.rename(columns={"md5": "id"}, inplace=True)
        news_df["mes"] = news_df["mes"].apply(lambda x: remove_sensitive_information(x))
        events_df = pd.merge(events_df, news_df, on="id", how="left")

        return events_df.to_dict(orient="records")

    async def save_events(self, events: List[Dict]):
        """保存事件生成结果"""
        events_data = []
        for event in events:
            links = [
                {
                    "id": id,
                    "title": event["titles"][index],
                    "link": event["links"][index],
                    "from": event["from"][index],
                }
                for index, id in enumerate(event["event_ids"])
            ]
            events_data.append(
                {
                    "event_id": event["event_id"],
                    "event_summary": event["event_summary"],
                    "content": event["content"],
                    "date": event["date"],
                    "title": event["title"],
                    "score": event["score"],
                    "links": links,
                }
            )

        await self.events_db.insert_events(events_data, type=self.type)

        return events_data

    async def generate_events(self):
        """执行事件生成"""
        try:
            task_logger.info("开始执行事件生成...")

            # 从数据库获取新闻事件列表
            events = await self.news_db.get_news_selection_data(
                start_time=self.start_time, end_time=self.end_time
            )
            if events:
                # 过滤新闻事件
                filtered_events = await self.get_filtered_events(events)
                # 事件整合提取
                events_integration = await self.events_integration_extract(
                    filtered_events
                )
                # 同一事件整合提炼
                same_event_integration = await self.same_event_integration(
                    events_integration
                )

                events_data = await self.save_events(same_event_integration)

                task_logger.info("事件生成完成")
                # 返回事件生成结果
                return events_data
            else:
                task_logger.error("没有找到新闻事件")
                return []
        except Exception as e:
            task_logger.error(f"事件生成失败: {str(e)}", exc_info=True)
            return []
