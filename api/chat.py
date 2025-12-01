import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

import requests
from fastapi import APIRouter, Body, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config.settings import DIFY_CONFIG
from logger import api_logger

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    inputs: Dict[str, Any] = {}
    response_mode: str = "streaming"  # streaming 或 blocking
    conversation_id: Optional[str] = None
    user: str
    files: Optional[List[Dict[str, Any]]] = []
    auto_generate_name: Optional[bool] = True


class FeedbackRequest(BaseModel):
    message_id: str
    rating: str  # like 或 dislike
    user: str
    content: Optional[str] = None


async def process_stream(response):
    """处理流式响应"""
    api_logger.info("开始处理流式响应")
    has_yielded_data = False
    message_id = None
    conversation_id = None
    task_id = None
    received_message_end = False

    def iter_content():
        nonlocal message_id, conversation_id, task_id, received_message_end
        buffer = ""

        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                chunk_str = chunk.decode("utf-8")
                # 将新块添加到缓冲区
                buffer += chunk_str

                # 查找并处理完整的SSE事件
                events = buffer.split("\n\n")
                # 保留最后一个可能不完整的事件
                buffer = events.pop() if events and not buffer.endswith("\n\n") else ""

                for event in events:
                    if event.startswith("data: "):
                        data = event[6:].strip()  # 移除'data: '前缀并删除前后空白
                        if data:
                            try:
                                # 解析JSON
                                json_data = json.loads(data)
                                event_type = json_data.get("event", "unknown")
                                api_logger.debug(f"处理事件: {event_type}")

                                # 提取关键信息
                                if json_data.get("id"):
                                    message_id = json_data.get("id")

                                if json_data.get("message_id"):
                                    message_id = json_data.get("message_id")

                                if json_data.get("conversation_id"):
                                    conversation_id = json_data.get("conversation_id")

                                if json_data.get("task_id"):
                                    task_id = json_data.get("task_id")

                                # 检查是否为结束事件
                                if (
                                    event_type == "message_end"
                                    or event_type == "workflow_finished"
                                ):
                                    received_message_end = True
                                    api_logger.info(
                                        f"接收到结束事件: {event_type}, message_id={message_id}"
                                    )

                                # 将事件传递给客户端
                                yield f"data: {data}\n\n"
                            except json.JSONDecodeError as e:
                                api_logger.error(
                                    f"JSON解析错误 ({str(e)}): {data[:100]}..."
                                )

                                # 尝试修复不完整的JSON并重试
                                try:
                                    # 尝试转义特殊字符
                                    fixed_data = data.replace("\\", "\\\\").replace(
                                        "\n", "\\n"
                                    )
                                    json.loads(fixed_data)
                                    yield f"data: {fixed_data}\n\n"
                                    api_logger.info("JSON已修复并成功解析")
                                except:
                                    # 如果修复尝试失败，仍发送原始数据
                                    yield f"data: {data}\n\n"

        # 处理缓冲区中剩余的数据
        if buffer and buffer.startswith("data: "):
            data = buffer[6:].strip()
            if data:
                try:
                    json_data = json.loads(data)
                    event_type = json_data.get("event", "unknown")

                    # 提取关键信息
                    if json_data.get("id"):
                        message_id = json_data.get("id")

                    if json_data.get("message_id"):
                        message_id = json_data.get("message_id")

                    if json_data.get("conversation_id"):
                        conversation_id = json_data.get("conversation_id")

                    if json_data.get("task_id"):
                        task_id = json_data.get("task_id")

                    # 检查是否为结束事件
                    if event_type == "message_end" or event_type == "workflow_finished":
                        received_message_end = True

                    yield f"data: {data}\n\n"
                except json.JSONDecodeError:
                    api_logger.error(
                        f"处理缓冲区剩余数据时JSON解析错误: {data[:100]}..."
                    )

    # 使用循环和asyncio.sleep让出控制权，实现异步流处理
    try:
        for chunk in iter_content():
            has_yielded_data = True
            yield chunk
            await asyncio.sleep(0)

        # 仅当没有收到结束事件时，才手动发送消息结束事件
        if has_yielded_data and not received_message_end and message_id:
            api_logger.info(
                "流式输出已完成，但未接收到结束事件，手动发送message_end事件"
            )

            end_event = {
                "event": "message_end",
                "task_id": task_id or "",
                "conversation_id": conversation_id or "",
                "message_id": message_id or "",
            }
            api_logger.info(f"手动发送消息结束事件: {end_event}")
            yield f"data: {json.dumps(end_event)}\n\n"

    except Exception as e:
        api_logger.error(f"流式处理过程中发生错误: {str(e)}")
        error_event = {"event": "error", "message": f"处理流时出错: {str(e)}"}
        yield f"data: {json.dumps(error_event)}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest = Body(...)):
    """
    本地向量数据库聊天对话

    - 支持普通对话和流式响应
    - 基于向量数据库进行RAG检索
    - 可以传递对话历史以保持上下文
    """
    from services.chat_service import chat_service
    
    api_logger.info(f"发送聊天请求: {request.query}")

    try:
        # 使用本地聊天服务
        result = await chat_service.chat(
            query=request.query,
            conversation_id=request.conversation_id,
            user_id=request.user,
            stream=(request.response_mode == "streaming")
        )

        if "error" in result:
            api_logger.error(f"聊天服务错误: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])

        if request.response_mode == "streaming":
            # 返回流式响应
            async def generate_stream():
                response_generator = result["response"]
                async for chunk in response_generator:
                    yield f"data: {json.dumps({'answer': chunk})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(generate_stream(), media_type="text/event-stream")
        else:
            # 返回普通响应，格式兼容Dify
            return {
                "event": "message",
                "message_id": result.get("message_id"),
                "conversation_id": result["conversation_id"],
                "mode": "chat",
                "answer": result["answer"],
                "metadata": {
                    "usage": {
                        "prompt_tokens": len(request.query.split()),
                        "completion_tokens": len(result["answer"].split()),
                        "total_tokens": len(request.query.split()) + len(result["answer"].split())
                    },
                    "retrieval": {
                        "position": 1
                    }
                },
                "created_at": int(datetime.now().timestamp())
            }

    except Exception as e:
        api_logger.error(f"处理聊天请求时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/{message_id}")
async def message_feedback(message_id: str, request: FeedbackRequest = Body(...)):
    """
    对聊天消息提供反馈（点赞/踩）
    """
    from services.chat_service import chat_service
    
    api_logger.info(f"发送消息反馈: {message_id}, 评分: {request.rating}")

    try:
        result = chat_service.feedback_message(
            message_id=message_id,
            rating=request.rating,
            content=request.content
        )
        
        return {
            "result": "success",
            "message_id": message_id,
            "rating": request.rating
        }
        
    except Exception as e:
        api_logger.error(f"处理反馈请求时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_chat_history(
    conversation_id: str, user: str, first_id: Optional[str] = None, limit: int = 20
):
    """
    获取聊天历史记录
    """
    from services.chat_service import chat_service
    
    api_logger.info(f"获取聊天历史: conversation_id={conversation_id}, user={user}")

    try:
        messages = chat_service.get_conversation_history(
            conversation_id=conversation_id,
            user_id=user,
            limit=limit
        )
        
        # 格式化为兼容Dify的格式
        formatted_messages = []
        for msg in messages:
            # 添加用户消息
            formatted_messages.append({
                "id": f"{msg['id']}_user",
                "conversation_id": conversation_id,
                "inputs": {},
                "query": msg["query"],
                "answer": "",
                "feedback": None,
                "retriever_resources": [],
                "created_at": msg["created_at"],
                "agent_based": False
            })
            
            # 添加助手回答
            formatted_messages.append({
                "id": f"{msg['id']}_assistant",
                "conversation_id": conversation_id,
                "inputs": {},
                "query": "",
                "answer": msg["answer"],
                "feedback": None,
                "retriever_resources": [],
                "created_at": msg["created_at"],
                "agent_based": False
            })
        
        return {
            "object": "list",
            "data": formatted_messages,
            "first_id": formatted_messages[0]["id"] if formatted_messages else None,
            "last_id": formatted_messages[-1]["id"] if formatted_messages else None,
            "has_more": False,
            "limit": limit
        }
        
    except Exception as e:
        api_logger.error(f"获取聊天历史时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def get_conversations(user: str, last_id: Optional[str] = None, limit: int = 20):
    """
    获取用户的对话列表
    """
    api_logger.info(f"获取用户对话列表: user={user}")

    headers = {"Authorization": f"Bearer {DIFY_CONFIG['chat_api_key']}"}

    params = {"user": user, "limit": limit}

    if last_id:
        params["last_id"] = last_id

    try:
        # 构建请求 URL
        url = f"{DIFY_CONFIG['base_url']}/v1/conversations"

        def do_get_conversations():
            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                api_logger.error(
                    f"Dify API 获取对话列表错误: {response.status_code}, {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code, detail=response.text
                )

            return response.json()

        result = await asyncio.to_thread(do_get_conversations)
        return result
    except Exception as e:
        api_logger.error(f"获取对话列表时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user: str):
    """
    删除特定对话
    """
    api_logger.info(f"删除对话: conversation_id={conversation_id}, user={user}")

    headers = {
        "Authorization": f"Bearer {DIFY_CONFIG['chat_api_key']}",
        "Content-Type": "application/json",
    }

    payload = {"user": user}

    try:
        # 构建请求 URL
        url = f"{DIFY_CONFIG['base_url']}/v1/conversations/{conversation_id}"

        def do_delete_conversation():
            response = requests.delete(url, headers=headers, json=payload)

            if response.status_code not in [200, 204]:
                api_logger.error(
                    f"Dify API 删除对话错误: {response.status_code}, {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code, detail=response.text
                )

            return {"result": "success"}

        result = await asyncio.to_thread(do_delete_conversation)
        return result
    except Exception as e:
        api_logger.error(f"删除对话时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 为了兼容前端直接调用 Dify API 的情况，添加一个中转的 v1 路径端点
@router.post("/v1/chat-messages")
async def chat_messages_proxy(request: Request):
    """
    Dify chat-messages API的代理端点
    """
    api_logger.info("接收到直接的chat-messages请求")

    # 读取请求体
    body = await request.json()

    headers = {
        "Authorization": f"Bearer {DIFY_CONFIG['chat_api_key']}",
        "Content-Type": "application/json",
    }

    try:
        # 构建请求 URL
        url = f"{DIFY_CONFIG['base_url']}/v1/chat-messages"

        # 确定是流式响应还是阻塞响应
        is_streaming = body.get("response_mode") == "streaming"

        if is_streaming:
            # 流式响应需要在线程池中执行
            def stream_request():
                return requests.post(url, headers=headers, json=body, stream=True)

            response = await asyncio.to_thread(stream_request)

            if response.status_code != 200:
                api_logger.error(
                    f"Dify API 错误: {response.status_code}, {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code, detail=response.text
                )

            return StreamingResponse(
                process_stream(response), media_type="text/event-stream"
            )
        else:
            # 阻塞式响应也需要在线程池中执行
            def blocking_request():
                response = requests.post(url, headers=headers, json=body)

                if response.status_code != 200:
                    api_logger.error(
                        f"Dify API 错误: {response.status_code}, {response.text}"
                    )
                    raise HTTPException(
                        status_code=response.status_code, detail=response.text
                    )

                return response.json()

            result = await asyncio.to_thread(blocking_request)
            return result

    except Exception as e:
        api_logger.error(f"处理中转请求时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 为了支持停止生成的功能
@router.post("/v1/chat-messages/{task_id}/stop")
async def stop_generation_proxy(task_id: str, request: Request):
    """
    停止生成API的代理端点
    """
    api_logger.info(f"接收到停止生成请求: task_id={task_id}")

    # 读取请求体
    body = await request.json()

    headers = {
        "Authorization": f"Bearer {DIFY_CONFIG['chat_api_key']}",
        "Content-Type": "application/json",
    }

    try:
        # 构建请求 URL
        url = f"{DIFY_CONFIG['base_url']}/v1/chat-messages/{task_id}/stop"

        # 使用线程池运行同步请求
        def do_stop_request():
            response = requests.post(url, headers=headers, json=body)

            if response.status_code != 200:
                api_logger.error(
                    f"Dify API 停止生成错误: {response.status_code}, {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code, detail=response.text
                )

            return response.json()

        result = await asyncio.to_thread(do_stop_request)
        return result
    except Exception as e:
        api_logger.error(f"处理停止生成请求时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# 添加文件上传的代理接口
@router.post("/v1/files/upload")
async def upload_file_proxy(request: Request):
    """
    文件上传API的代理端点
    """
    api_logger.info("接收到文件上传请求")

    # 获取表单数据
    form_data = await request.form()

    # 准备请求到Dify API
    headers = {"Authorization": f"Bearer {DIFY_CONFIG['chat_api_key']}"}

    try:
        # 从表单中获取文件
        file = form_data.get("file")
        user = form_data.get("user")

        if not file:
            raise HTTPException(status_code=400, detail="文件不能为空")

        if not user:
            raise HTTPException(status_code=400, detail="用户ID不能为空")

        # 读取文件内容
        file_content = await file.read()

        # 由于requests不是异步的，使用run_in_executor在线程池中执行请求
        def do_upload():
            files = {"file": (file.filename, file_content, file.content_type)}
            data = {"user": user}

            # 构建请求URL
            url = f"{DIFY_CONFIG['base_url']}/v1/files/upload"

            response = requests.post(url, headers=headers, files=files, data=data)

            if response.status_code != 200:
                api_logger.error(
                    f"Dify API 文件上传错误: {response.status_code}, {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code, detail=response.text
                )

            return response.json()

        # 在线程池中执行同步请求
        result = await asyncio.to_thread(do_upload)
        return result

    except HTTPException as e:
        raise e
    except Exception as e:
        api_logger.error(f"处理文件上传请求时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
