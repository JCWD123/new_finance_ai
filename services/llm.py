import json
from typing import List, Tuple

import openai
from openai import BadRequestError

from config.settings import LLM_SETTINGS
from logger import token_logger, task_logger

ModelName = LLM_SETTINGS["model"]
ApiKey = LLM_SETTINGS["api_key"]
BaseUrl = LLM_SETTINGS["base_url"]


class LLMService:
    def __init__(
        self,
        model_name=ModelName,
        api_key=ApiKey,
        base_url=BaseUrl,
    ):
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.model = model_name

    def call_llm(
        self, messages: List[dict], max_retries: int = 3, timeout: tuple = None
    ) -> Tuple:
        """统一调用OpenAI接口"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                timeout=timeout,
                # response_format={"type": "json_object"},
            )
            token_logger.info(
                f"调用LLM接口，token使用情况：{response.usage.total_tokens}"
            )
        except BadRequestError as e:
            # 处理BadRequestError异常
            return "BadRequestError", False

        think_response = response.choices[0].message.model_extra
        retries = 0
        while retries < max_retries:
            json_str = (
                response.choices[0]
                .message.content.strip()
                .strip("```")
                .lstrip("json")
                .strip()
            )
            try:
                json_response = json.loads(json_str)
                break
            except json.decoder.JSONDecodeError:
                messages += [
                    {
                        "role": "assistant",
                        "content": json_str,
                    },
                    {
                        "role": "user",
                        "content": "请严格遵循JSON格式输出，直接返回有效的JSON对象，不要包含任何额外文本或Markdown代码块",
                    },
                ]
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        timeout=timeout,
                    )
                    token_logger.info(
                        f"调用LLM接口，token使用情况：{response.usage.total_tokens}"
                    )
                except BadRequestError as e:
                    # 处理BadRequestError异常
                    return "BadRequestError", False
                retries += 1
        else:
            task_logger.error(
                f"无法解析JSON响应，请检查LLM的输出格式是否正确: {json_str}"
            )
            json_response = {}
        return think_response, json_response
