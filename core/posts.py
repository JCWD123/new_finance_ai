from collections import Counter
from datetime import datetime
from itertools import chain
from typing import List, Dict

import pandas as pd

from core.event import EventProcessor
from logger import task_logger
from models.database import PostsDB, UserProfileDB, NewsDB
from prompt.posts import *
from prompt.util import OutputFormatConstraint
from services.llm import LLMService
from utils.task_utils import TaskManager
from utils.time_utils import calculate_base_time
from utils.html_parser import HTMLContentProcessor


class PostsProcessor:
    """历史发文处理逻辑"""

    def __init__(self, type: str = "ReadMorning"):
        self.type = type
        # 不再直接创建MongoDBService实例，而是使用数据库模型类
        self.posts_db = PostsDB()
        self.news_db = NewsDB()
        self.event_processor = EventProcessor()
        # 使用posts_db实例中的mongodb连接
        self.mongodb = self.posts_db.mongodb
        self.llm = LLMService()
        self.task_mgr = TaskManager()
        self.now = datetime.now()

    async def get_filtered_posts(self, posts: List[Dict]) -> List[Dict]:
        """过滤历史文章"""
        posts_df = pd.DataFrame(posts)
        ids = posts_df["md5"].tolist()
        posts_analysis_list = self.mongodb.batch_fetch_by_ids(
            collection_name=self.posts_db.PostsAnalysisDB, id_list=ids
        )
        if posts_analysis_list:
            posts_analysis_df = pd.DataFrame(posts_analysis_list)
            if self.type == "Essence":
                ids = posts_analysis_df[posts_analysis_df["content_analysis"].notna()][
                    "id"
                ].tolist()
            else:
                ids = posts_analysis_df[
                    (posts_analysis_df["coreMarketRankings"].notna())
                    & (posts_analysis_df["marketAnalysis"].notna())
                    & (posts_analysis_df["filter_logic"].notna())
                    & (posts_analysis_df["content_analysis"].notna())
                ]["id"].tolist()
            posts = [post for post in posts if post["md5"] not in ids]

        return posts

    async def extract_posts(self, posts: List[Dict] = [],limit:int = 100):
        """处理历史文章"""
        try:
            task_logger.info("开始处理历史文章...")

            # 获取历史发文
            if posts == []:
                posts = await self.posts_db.get_posts(type=self.type, limit=limit)

            if not posts:
                task_logger.info("没有找到历史发文，跳过处理")
                return {}

            posts = await self.get_filtered_posts(posts)
            task_logger.info(f"找到{len(posts)}条未分析的历史发文")

            results = await self.task_mgr.process_tasks(
                self._process_post_batch,
                posts,
            )

            # 过滤掉None结果
            results = [r for r in results if r]
            task_logger.info(f"成功处理{len(results)}条历史文章")
            task_logger.info("历史文章处理完成")
            return results
        except Exception as e:
            task_logger.error(f"历史文章处理失败: {str(e)}", exc_info=True)
            return []

    async def _process_post_batch(self, post: Dict) -> Dict:
        """处理单批次历史发文"""
        try:
            if self.type == "ReadMorning" or self.type == "LogicalReview":
                # 市场主题分析
                market_analysis = await self._analyze_market(post)
                # 逻辑主题分析
                logic_analysis = await self._analyze_user_logic(post)
                # 内容观点提炼
                content_analysis = await self._analyze_content(post)
            else:
                market_analysis = {}
                logic_analysis = None
                content_analysis = await self._analyze_serums(post)

            result = {
                "id": post.get("md5"),
                "coreMarketRankings": market_analysis.get("coreMarketRankings", None),
                "marketAnalysis": market_analysis.get("marketAnalysis", None),
                "filter_logic": logic_analysis,
                "content_analysis": content_analysis.get("analyze_content", None),
                "type": self.type,
                "date": post.get("date"),
            }

            # 保存到数据库
            if not self.mongodb.check_id_exists(
                collection_name=self.posts_db.PostsAnalysisDB, id=post.get("md5")
            ):
                await self.posts_db.save_posts_analysis(result)
            else:
                data = {
                    "coreMarketRankings": market_analysis.get(
                        "coreMarketRankings", None
                    ),
                    "marketAnalysis": market_analysis.get("marketAnalysis", None),
                    "filter_logic": logic_analysis,
                    "content_analysis": content_analysis.get("analyze_content", None),
                }
                await self.posts_db.update_posts_analysis(id=post.get("md5"), data=data)
            return result
        except Exception as e:
            task_logger.error(f"处理历史发文失败: {str(e)}", exc_info=True)
            return {}

    async def _analyze_market(self, post: Dict) -> Dict:
        """市场分析处理"""
        try:
            task_logger.info(f"开始执行市场分析: {post.get('md5')}")

            full_prompt = ThemeAnalysisPrompt.format(posts=post, OutputFormatConstraint=OutputFormatConstraint)
            messages = [
                {"role": "system", "content": ThemeAnalysisSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]

            _, json_response = self.llm.call_llm(messages=messages)

            task_logger.info(f"市场分析完成: {post.get('md5')}")
            return json_response
        except Exception as e:
            task_logger.error(f"市场分析失败: {str(e)}", exc_info=True)
            return {}

    async def _analyze_user_logic(self, post: Dict) -> Dict:
        """用户逻辑分析"""
        try:
            task_logger.info(f"开始执行用户逻辑分析: {post.get('md5')}")
            end_time, start_time = calculate_base_time(
                datetime.fromtimestamp(post["date"]), type=self.type
            )
            events = await self.news_db.get_news_selection_data(
                start_time=start_time, end_time=end_time
            )
            if not events:
                task_logger.info(
                    f"没有找到{self.type}事件，跳过用户逻辑分析: {post.get('md5')}"
                )
                return None
            events = await self.event_processor.get_filtered_events(events)
            events = [
                {
                    "id": event["id"],
                    "title": event["title"],
                    "mes": event["mes"],
                    "date": datetime.fromtimestamp(event["date"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
                for event in events
            ]
            full_prompt1 = ReverseLogicalReasoningPrompt.format(
                reference_text=post["mes"].strip(), count=len(events), data_list=events, OutputFormatConstraint=OutputFormatConstraint
            )
            messages1 = [
                {"role": "system", "content": ReverseLogicalReasoningSystemPrompt},
                {"role": "user", "content": full_prompt1},
            ]
            _, json_response1 = self.llm.call_llm(messages=messages1)

            full_prompt2 = FilterLogicalReasoningPrompt.format(
                candidate_news=events, selected_news=json_response1, OutputFormatConstraint=OutputFormatConstraint
            )
            messages2 = [
                {"role": "system", "content": FilterLogicalReasoningSystemPrompt},
                {"role": "user", "content": full_prompt2},
            ]
            _, json_response2 = self.llm.call_llm(messages=messages2)
            task_logger.info(f"用户逻辑分析完成: {post.get('md5')}")
            return json_response2
        except Exception as e:
            task_logger.error(f"用户逻辑分析失败: {str(e)}", exc_info=True)
            return None

    async def _analyze_content(self, post: Dict) -> Dict:
        """内容提炼"""
        try:
            task_logger.info(f"开始执行内容分析: {post.get('md5')}")
            full_prompt = BlogExtractionPrompt.format(post=post, OutputFormatConstraint=OutputFormatConstraint)
            messages = [
                {"role": "system", "content": BlogExtractionSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            _, json_response = self.llm.call_llm(messages=messages)
            task_logger.info(f"内容提炼完成: {post.get('md5')}")
            return {"analyze_content": json_response}
        except Exception as e:
            task_logger.error(f"内容提炼失败: {str(e)}", exc_info=True)
            return {}

    async def _analyze_serums(self, post: Dict) -> Dict:
        """精华提炼"""
        try:
            task_logger.info(f"开始执行精华提炼: {post.get('md5')}")
            full_prompt = HighlightExtractionPrompt.format(post=post, OutputFormatConstraint=OutputFormatConstraint)
            messages = [
                {"role": "system", "content": HighlightExtractionSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            _, json_response = self.llm.call_llm(messages=messages)
            task_logger.info(f"精华提炼完成: {post.get('md5')}")

            return {"analyze_content": json_response}
        except Exception as e:
            task_logger.error(f"精华提炼失败: {str(e)}", exc_info=True)
            return {}

    async def financial_market_analysis(self, posts: dict = {}) -> Dict:
        """金融行情市场分析"""
        try:
            read_morning = posts.get("ReadMorning", [])
            logical_review = posts.get("LogicalReview", [])
            if not read_morning and not logical_review:
                task_logger.info("没有找到早间必读或逻辑复盘文章，跳过金融行情市场分析")
                return {}
            task_logger.info("开始执行金融行情市场分析...")
            full_prompt = FinancialMarketAnalysisPrompt.format(
                read_morning=read_morning[:3], logical_review=logical_review[:3], OutputFormatConstraint=OutputFormatConstraint
            )
            messages = [
                {"role": "system", "content": FinancialMarketAnalysisSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            _, json_response = self.llm.call_llm(messages=messages)
            task_logger.info("金融行情市场分析完成")
            return json_response
        except Exception as e:
            task_logger.error(f"金融行情市场分析失败: {str(e)}", exc_info=True)
            return {}

    async def financial_models_analysis(self, posts: dict = {}) -> Dict:
        """金融板块分析"""
        try:
            read_morning = posts.get("ReadMorning", [])
            logical_review = posts.get("LogicalReview", [])
            if not read_morning and not logical_review:
                task_logger.info("没有找到早间必读或逻辑复盘文章，跳过金融板块分析")
                return {}
            task_logger.info("开始执行金融板块分析...")
            full_prompt = ModelsAnalysisPrompt.format(
                read_morning=read_morning[:3], logical_review=logical_review[:3], OutputFormatConstraint=OutputFormatConstraint
            )
            messages = [
                {"role": "system", "content": ModelsAnalysisSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            _, json_response = self.llm.call_llm(messages=messages)
            task_logger.info("金融板块分析完成")
            return json_response
        except Exception as e:
            task_logger.error(f"金融板块分析失败: {str(e)}", exc_info=True)
            return {}

    async def _analyze_img_content(self, post: Dict) -> Dict:
        """图片内容提炼"""
        try:
            task_logger.info(f"开始执行图片内容提炼: {post.get('md5')}")
            content = post.get("mes", "")
            
            # 创建HTML处理器
            html_processor = HTMLContentProcessor()
            
            # 处理文章中的div块
            processed_content, div_blocks = await html_processor.process_article_content(content)
            
            # 收集所有图片分析结果
            img_analyses = []
            successful_analyses = 0
            failed_analyses = 0
            
            for div_block in div_blocks:
                img_analysis = div_block.get('img_analysis', {})
                if img_analysis.get('success'):
                    img_analyses.append({
                        'img_url': img_analysis.get('img_url'),
                        'analysis_result': img_analysis.get('analysis_result', {}),
                        'analysis_text': img_analysis.get('analysis_text'),
                        'content_type': img_analysis.get('content_type'),
                        'key_points': img_analysis.get('key_points', []),
                        'data_insights': img_analysis.get('data_insights'),
                        'think_response': img_analysis.get('think_response')
                    })
                    successful_analyses += 1
                else:
                    img_analyses.append({
                        'img_url': img_analysis.get('img_url'),
                        'error': img_analysis.get('error'),
                        'success': False
                    })
                    failed_analyses += 1
            
            result = {
                "processed_content": processed_content,
                "image_analyses": img_analyses,
                "div_count": len(div_blocks),
                "successful_analyses": successful_analyses,
                "failed_analyses": failed_analyses
            }
            
            task_logger.info(f"图片内容提炼完成，处理了 {len(div_blocks)} 个图片，成功 {successful_analyses} 个，失败 {failed_analyses} 个")
            return {"analyze_content": result}
            
        except Exception as e:
            task_logger.error(f"图片内容提炼失败: {str(e)}", exc_info=True)
            return {}


class PostsService:
    """历史发文分析服务类"""

    def __init__(self):
        self.processor = PostsProcessor()

    async def extract_posts(self, posts: List[Dict] = [],limit:int = 100):
        """提取历史发文"""
        return await self.processor.extract_posts(posts,limit)

    async def financial_market_analysis(self, posts: dict = {}) -> Dict:
        """金融行情市场分析"""
        return await self.processor.financial_market_analysis(posts)

    async def financial_models_analysis(self, posts: dict = {}) -> Dict:
        """金融板块分析"""
        return await self.processor.financial_models_analysis(posts)


class UserProfileProcessor:
    """用户画像处理"""

    def __init__(self, type: str = "ReadMorning"):
        self.type = type
        self.posts_db = PostsDB()
        self.user_db = UserProfileDB()
        self.mongodb = self.posts_db.mongodb
        self.llm = LLMService()
        self.task_mgr = TaskManager()
        self.now = datetime.now()

    async def _get_standardized_subtopics(self, sub_topics: List[str]) -> List[str]:
        """标准化子主题"""
        try:
            full_prompt = SubjectStandardizationPrompt.format(sub_topics=sub_topics, OutputFormatConstraint=OutputFormatConstraint)
            messages = [
                {"role": "system", "content": SubjectStandardizationSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            _, json_response = self.llm.call_llm(messages=messages)
            return [
                i["standardized_subtopic"]
                for i in json_response["standardized_subtopics"]
            ]
        except Exception as e:
            task_logger.error(f"标准化子主题失败: {str(e)}", exc_info=True)
            return {}

    async def _get_topics(self, posts_analysis_df: pd.DataFrame) -> Dict:
        """获取主题"""
        try:
            coreMarketRankings = posts_analysis_df["coreMarketRankings"].tolist()
            marketAnalysis = posts_analysis_df["marketAnalysis"].tolist()
            all_themes = []
            for index, core in enumerate(coreMarketRankings):
                core = set(
                    [
                        i
                        for i in (
                            core + [d.get("theme", "") for d in marketAnalysis[index]]
                        )
                        if i
                    ]
                )
                all_themes.append(core)
            all_themes = list(chain.from_iterable(all_themes))
            all_themes = Counter(all_themes)

            # 构建主题词典
            topics = {}
            for index, data in enumerate(marketAnalysis):
                for sub_topic in data:
                    theme = sub_topic.get("theme", "")
                    if not theme:
                        continue

                    if theme not in topics:
                        topics[theme] = {
                            "frequency": all_themes[theme],
                            "subTopics": sub_topic.get("subTopics", []),
                        }
                    else:
                        topics[theme]["subTopics"].extend(
                            sub_topic.get("subTopics", [])
                        )
            # 子主题标准化处理
            for topic in topics:
                sub_topics_list = topics[topic]["subTopics"]
                # 将子主题列表分批处理，每批50个
                sub_topics_list = [
                    sub_topics_list[i : i + 50]
                    for i in range(0, len(sub_topics_list), 50)
                ]
                topics[topic]["subTopics"] = []

                # 对每批子主题进行标准化处理
                results = await self.task_mgr.process_tasks(
                    self._get_standardized_subtopics,
                    sub_topics_list,
                    use_processes=False,
                )
                topics[topic]["subTopics"].extend(list(chain.from_iterable(results)))
                # 去重处理
                topics[topic]["subTopics"] = list(set(topics[topic]["subTopics"]))
            return topics
        except Exception as e:
            task_logger.error(f"获取主题失败: {str(e)}", exc_info=True)
            return {}

    async def _get_user_topic_profile(self, topics: dict) -> Dict:
        """获取用户市场主题画像"""
        try:
            full_prompt = UserInterestPrompt.format(topics=topics, OutputFormatConstraint=OutputFormatConstraint)
            messages = [
                {"role": "system", "content": UserInterestSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            _, json_response = self.llm.call_llm(messages=messages)
            return json_response["user_topic_profile"]
        except Exception as e:
            task_logger.error(f"获取用户画像失败: {str(e)}", exc_info=True)
            return {}

    async def _get_user_logic_profile(self, posts_analysis_df: pd.DataFrame) -> Dict:
        """获取用户逻辑画像"""
        try:
            filter_logics = posts_analysis_df["filter_logic"].tolist()
            
            # 统计None值数量
            none_count = sum(1 for item in filter_logics if item is None)
            total_count = len(filter_logics)
            none_ratio = none_count / total_count if total_count > 0 else 0
            
            # 如果None值超过10%，不执行大模型生成
            if none_ratio > 0.1:
                task_logger.info(f"历史发文分析中None值比例过高({none_ratio:.2%})，跳过用户逻辑画像生成,从数据库中获取")
                user_logic_profile = await self.user_db.get_logic_profile()
                return user_logic_profile
            
            # 去除None值
            valid_filter_logics = [logic for logic in filter_logics if logic is not None]
            task_logger.info(f"过滤掉{none_count}个None值后，剩余{len(valid_filter_logics)}个有效逻辑记录")
            
            # 执行大模型生成
            full_prompt = UserLogicPrompt.format(filter_logics=valid_filter_logics, OutputFormatConstraint=OutputFormatConstraint)
            messages = [
                {"role": "system", "content": UserLogicSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            _, json_response = self.llm.call_llm(messages=messages)

            return json_response
        except Exception as e:
            task_logger.error(f"获取用户逻辑画像失败: {str(e)}", exc_info=True)
            return {}

    async def _get_user_writing_style(self, posts: List[Dict] = []) -> Dict:
        """获取用户写作风格"""
        try:
            if posts == []:
                posts = await self.posts_db.get_posts(type=self.type, limit=20)
            if not posts:
                task_logger.info("没有找到历史发文，跳过获取用户写作风格")
                return {}
            full_prompt = BloggerPortraitPrompt.format(posts=posts, OutputFormatConstraint=OutputFormatConstraint)
            messages = [
                {"role": "system", "content": BloggerPortraitSystemPrompt},
                {"role": "user", "content": full_prompt},
            ]
            _, json_response = self.llm.call_llm(messages=messages)
            return json_response["writing_style"]

        except Exception as e:
            task_logger.error(f"获取用户写作风格失败: {str(e)}", exc_info=True)
            return {}

    async def extract_user_profile(self, posts_analysis: List[Dict] = []):
        """提取用户画像"""
        try:
            task_logger.info("开始提取用户画像...")
            if posts_analysis == []:
                posts_analysis = await self.posts_db.get_posts_analysis(
                    type=self.type, limit=100
                )
            if not posts_analysis:
                task_logger.info("没有找到历史发分析结果，跳过提取用户画像")
                return {}

            posts_analysis_df = pd.DataFrame(posts_analysis)
            topics = await self._get_topics(posts_analysis_df)
            user_topic_profile = await self._get_user_topic_profile(topics)
            user_logic_profile = await self._get_user_logic_profile(posts_analysis_df)
            writing_style = await self._get_user_writing_style()
            user_profile_data = {
                "writing_style": writing_style,
                "topics": topics,
                "topic_profile": user_topic_profile,
                "logic_profile": user_logic_profile,
            }

            await self.user_db.save_user_profile(user_profile_data)

            task_logger.info("用户画像提取完成")
            return topics, user_topic_profile, user_logic_profile
        except Exception as e:
            task_logger.error(f"用户画像提取失败: {str(e)}", exc_info=True)
            return {}
