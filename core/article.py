import re
import time
from datetime import datetime
from typing import List, Dict

import requests

from config.settings import FEISHU_CONFIG
from logger import task_logger
from models.database import EventsArticleDB, UserProfileDB, MarketDB, PostsDB
from prompt.article import *
from prompt.util import *
from services.llm import LLMService
from utils.time_utils import calculate_base_time
from utils.tools import extract_square_bracket_contents, process_text


class ArticleGenerator:
    """文章生成核心逻辑"""

    def __init__(self, article_type: str):
        self.article_type = article_type
        self.events_db = EventsArticleDB()
        self.user_db = UserProfileDB()
        self.market_db = MarketDB()
        self.posts_db = PostsDB()
        self.llm = LLMService()
        self.end_time, self.start_time = calculate_base_time(
            datetime.now(), type=self.article_type
        )

    async def generate_read_morning(self) -> str:
        """生成早间必读文章"""
        try:
            task_logger.info(f"开始生成早间必读文章: {self.article_type}")
            # 获取文章参数
            history_posts = await self.posts_db.get_posts(self.article_type)
            domain, posts = extract_square_bracket_contents(history_posts)
            events_data = await self.events_db.get_events_articles(self.article_type)
            id = events_data[0].get("id")
            events = events_data[0].get("events", [])
            key_points = [
                {
                    "event_summary": event["event_summary"],
                    "content": event["content"],
                    "score": event["score"],
                    "date": event["date"],
                }
                for event in events
            ][:30]
            writing_style = await self.user_db.get_writing_style()
            market_data = await self.market_db.get_exponent()
            # 生成文章内容
            article = await self.generate_llm_article(
                key_points=key_points,
                writing_style=writing_style,
                reference_contents=posts[:5],
                market_data=market_data,
            )
            # 评估生成内容
            evaluation_report, article = await self.get_evaluation_report(
                key_points=key_points,
                writing_style=writing_style,
                reference_contents=posts[:5],
                generated_content=article,
            )
            # 事件追踪
            article = await self.get_traced_content(
                content=article,
                points=events,
                market_data=market_data,
            )
            article = process_text(article, domain)
            # 保存生成结果
            await self.events_db.update_article(id=id, article=article)

            return article
        except Exception as e:
            task_logger.error(f"生成早间必读文章失败: {str(e)}")
            raise

    async def generate_logical_review(self) -> str:
        """生成逻辑复盘文章"""
        try:
            task_logger.info(f"开始生成逻辑复盘文章: {self.article_type}")
            # 获取文章参数
            history_posts = await self.posts_db.get_posts(self.article_type)
            domain, history_posts = extract_square_bracket_contents(history_posts)
            read_morning_posts = await self.posts_db.get_posts("ReadMorning")
            _, posts = extract_square_bracket_contents(read_morning_posts)
            post = posts[0].get("mes", "")
            events_data = await self.events_db.get_events_articles(self.article_type)
            id = events_data[0].get("id")
            events = events_data[0].get("events", [])
            key_points = [
                {
                    "event_summary": event["event_summary"],
                    "content": event["content"],
                    "score": event["score"],
                    "date": event["date"],
                }
                for event in events
            ][:30]
            market_data = await self.market_db.get_quotes()
            # 生成文章内容
            task_logger.info("正在执行逻辑复盘内容生成......")

            full_prompt = LogicReviewPrompt.format(
                events=events,
                market_data=market_data,
                ReadMorning_articles=post,
                style_reference_article=history_posts[:10],
                constraints=Constraint,
                OutputFormatConstraint=OutputFormatConstraint,
            )
            messages = [
                {"role": "system", "content": LogicReviewSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            # 生成逻辑复盘文章
            while True:
                try:
                    think_response, json_response = self.llm.call_llm(messages=messages)
                    if json_response:
                        article = json_response["content"].strip()
                        break
                    else:
                        task_logger.error(f"生成逻辑复盘文章时发生错误,重新尝试...")
                except ValueError as e:
                    task_logger.error(f"生成逻辑复盘文章时发生错误: {str(e)}")
                time.sleep(60)
            # 事件追踪
            article = await self.get_traced_content(
                content=article,
                points=events,
                market_data=market_data,
            )
            article = process_text(article, domain)
            # 保存生成结果
            await self.events_db.update_article(id=id, article=article)

            return article
        except Exception as e:
            task_logger.error(f"生成逻辑复盘文章失败: {str(e)}")
            raise

    async def generate_llm_article(
        self,
        key_points: List,
        writing_style: dict,
        reference_contents: list,
        market_data: List[Dict],
        max_retries: int = 3,
    ) -> str:
        """生成文章"""
        task_logger.info("正在执行生成文章......")
        full_prompt = ContentGenerationPrompt.format(
            key_points=key_points,
            prices=market_data,
            writing_style=writing_style,
            reference_contents=reference_contents,
            constraint=Constraint,
            OutputFormatConstraint=OutputFormatConstraint,
        )
        messages = [
            {"role": "system", "content": ContentGenerationSystemPrompt},
            {"role": "user", "content": full_prompt},
        ]

        content_response = self.llm.call_llm(messages=messages)[1]
        if content_response:
            content = content_response["content"].strip()

        if len(content) < 1500 and max_retries > 0:
            task_logger.info(f"生成的文章长度不足，重新生成: {self.article_type}")
            messages += [
                {
                    "role": "assistant",
                    "content": content,
                },
                {
                    "role": "user",
                    "content": CallbackCharacter.format(
                        content_length=len(content),
                        writing_style=writing_style,
                        constraint=Constraint,
                        reference_contents=reference_contents,
                        OutputFormatConstraint=OutputFormatConstraint,
                    ),
                },
            ]
            content_response = self.llm.call_llm(messages=messages)[1]
            if content_response:
                content = content_response["content"].strip()
            if len(content) < 1500:
                content = await self.generate_llm_article(
                    key_points,
                    writing_style,
                    reference_contents,
                    market_data,
                    max_retries=max_retries - 1,
                )

        # 处理生成的内容
        article = process_text(content)

        return article

    async def get_evaluation_report(
        self,
        key_points: List,
        writing_style: dict,
        reference_contents: list,
        generated_content: str,
        max_retries: int = 3,
    ):
        task_logger.info("正在执行内容质量评估......")
        full_prompt = AssessmentQualityStyleMigrationPrompt.format(
            key_points=key_points,
            reference_contents=reference_contents,
            generated_content=generated_content,
            OutputFormatConstraint=OutputFormatConstraint,
        )
        messages = [
            {"role": "system", "content": AssessmentQualityStyleMigrationSystemPrompt},
            {"role": "user", "content": full_prompt},
        ]
        think_response, evaluation_response = self.llm.call_llm(messages=messages)
        if evaluation_response:
            evaluation_report = evaluation_response["EvaluationReport"]
            overall_score = float(evaluation_report["OverallScore"])
            if overall_score < 85 and max_retries > 0:
                task_logger.info(
                    f"生成内容质量综合得分:{overall_score}，继续执行风格迁移质量评估和内容生成引擎......"
                )
                messages += [
                    {"role": "assistant", "content": evaluation_report},
                    {
                        "role": "user",
                        "content": CallQualityGenrationPrompt.format(
                            constraint=Constraint,
                            OutputFormatConstraint=OutputFormatConstraint,
                        ),
                    },
                ]
                try:
                    _, call_quality_genration = self.llm.call_llm(messages=messages)
                    if call_quality_genration:
                        generated_content = call_quality_genration["content"].strip()
                except Exception as e:
                    task_logger.error(
                        f"生成内容质量评估回调生成文章时发生错误: {str(e)}"
                    )
                evaluation_report, generated_content = await self.get_evaluation_report(
                    key_points,
                    writing_style,
                    reference_contents,
                    generated_content,
                    max_retries=max_retries - 1,
                )
        else:
            evaluation_report, generated_content = await self.get_evaluation_report(
                key_points,
                writing_style,
                reference_contents,
                generated_content,
                max_retries=max_retries - 1,
            )

        return evaluation_report, generated_content

    async def get_traced_content(
        self, content: str, points: list, market_data: List[Dict]
    ):
        events = [
            {
                "id": point["event_id"],
                "event_summary": point["event_summary"],
                "content": point["content"],
                "date": point["date"],
            }
            for point in points
        ]
        while True:
            task_logger.info("正在执行内容事件追踪......")

            full_prompt = ContentEventTracePrompt.format(
                content=content,
                events=events,
                market_data=market_data,
                OutputFormatConstraint=OutputFormatConstraint,
            )
            messages = [
                {"role": "system", "content": ContentEventTraceSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]

            think_response, json_response = self.llm.call_llm(messages=messages)
            if not json_response:
                task_logger.error(
                    "事件追踪时发生错误，模型上下文输入超限，取消正文内容输入，重新执行......"
                )
                if events[0].get("content", None) is None:
                    events = events[:-5]
                else:
                    events = [
                        {
                            "id": point["event_id"],
                            "event_summary": point["event_summary"],
                            # "content": point["content"],
                            "date": point["date"],
                        }
                        for point in points
                    ]
            else:
                break

        traced_content = json_response["traced_content"]
        traced_event_ids = re.findall(r"<([a-f0-9]+)>", traced_content)
        events_ids = [i["id"] for i in events]
        for event_id in traced_event_ids:
            if event_id not in events_ids:
                task_logger.info(f"Event ID {event_id} not found in events.")
                traced_content = traced_content.replace(f"<{event_id}>", "")
            else:
                task_logger.info(f"Event ID {event_id} found in events.")
                traced_content = traced_content.replace(
                    f"<{event_id}>",
                    # f'<span class="event-reference" onclick="fetchNewsDetail(\'{event_id}\')">查看详情</span>',
                    f'<span class="event-reference" data-news-id="{event_id}">查看详情</span>',
                )

        return traced_content


class ArticleService(ArticleGenerator):
    """文章服务类"""

    def __init__(self, article_type: str):
        super().__init__(article_type)
        self.today_date = datetime.now().date()

    async def get_article(self) -> str:
        """获取文章"""
        task_logger.info(f"获取文章: {self.article_type}")
        events_articles = await self.events_db.get_events_articles(self.article_type)
        _, article, create_time = (
            events_articles[0].get("events", []),
            events_articles[0].get("content", ""),
            events_articles[0].get("create_time", None),
        )
        if (
            create_time is not None
            and datetime.fromtimestamp(create_time).date() == self.today_date
        ):
            return article

        return

    async def generate_article(self) -> str:
        """生成文章"""
        while True:
            try:
                if self.article_type == "ReadMorning":
                    article = await self.generate_read_morning()
                    return article
                elif self.article_type == "LogicalReview":
                    article = await self.generate_logical_review()
                    return article
                else:
                    task_logger.info(f"文章类型不支持: {self.article_type}")
                    return
            except Exception as e:
                task_logger.error(f"生成文章失败: {str(e)}")
                time.sleep(60)

    async def send_feishu_message(self, message: str):
        """发送飞书消息"""
        url = FEISHU_CONFIG["app_url"]
        data = {"generated_content": message.replace("查看详情", "")}
        response = requests.post(url, json=data)

        return response.json()
