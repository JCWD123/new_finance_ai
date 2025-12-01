import json
import os
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime

# 修复tokenizers多进程警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from logger import task_logger
from services.vector_service import DocumentManager
from services.llm import LLMService
from services.deepseek_processor import DeepSeekProcessor


class LocalChatService:
    """基于本地向量数据库的聊天服务，替换Dify聊天功能"""
    
    def __init__(self):
        self.doc_manager = DocumentManager()
        self.llm = LLMService()
        self.conversation_history = {}  # 存储对话历史
        
    def _generate_conversation_id(self) -> str:
        """生成对话ID"""
        return f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(datetime.now()) % 10000}"
    
    def _build_rag_context(self, query: str, k: int = 3) -> str:
        """构建RAG上下文"""
        try:
            # 搜索相关文档
            results = self.doc_manager.search_related_posts(query=query, k=k)
            
            if not results:
                return "没有找到相关的历史文章参考。"
            
            context_parts = []
            for i, result in enumerate(results, 1):
                metadata = result.get("metadata", {})
                post_type = metadata.get("type", "未知类型")
                date = metadata.get("date", "")
                
                if isinstance(date, (int, float)):
                    date_str = datetime.fromtimestamp(date).strftime("%Y-%m-%d")
                else:
                    date_str = str(date)
                
                context_parts.append(
                    f"参考文章{i} ({post_type}, {date_str}):\n"
                    f"相似度: {result['score']:.3f}\n"
                    f"内容片段: {result.get('chunk_hit', result['content'][:300])}...\n"
                )
            
            return "\n".join(context_parts)
            
        except Exception as e:
            task_logger.error(f"构建RAG上下文失败: {str(e)}")
            return "获取参考资料时出现错误。"
    
    def _build_chat_prompt(self, query: str, context: str, conversation_history: List[Dict] = None) -> List[Dict]:
        """构建聊天提示词"""
        system_prompt = """你是一个专业的金融AI助手，专门分析金融市场和投资策略。

你的职责：
1. 基于提供的历史文章和市场数据，回答用户的金融相关问题
2. 提供专业、客观的金融分析和建议
3. 引用相关的历史文章作为分析依据
4. 保持专业的金融术语使用，但确保普通用户也能理解

回答要求：
- 基于提供的参考资料进行分析
- 如果没有相关资料，明确说明并提供一般性的专业建议
- 避免给出具体的投资建议，而是提供分析框架
- 保持客观中立的立场
"""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加对话历史
        if conversation_history:
            for msg in conversation_history[-6:]:  # 只保留最近6轮对话
                messages.append(msg)
        
        # 添加当前查询和上下文
        user_content = f"""基于以下参考资料回答问题：

参考资料：
{context}

用户问题：{query}

请基于上述参考资料进行分析和回答。如果参考资料不足以回答问题，请说明并提供一般性的专业建议。"""
        
        messages.append({"role": "user", "content": user_content})
        
        return messages
    
    async def chat(
        self, 
        query: str, 
        conversation_id: Optional[str] = None,
        user_id: str = "default_user",
        stream: bool = False
    ) -> Dict:
        """处理聊天请求"""
        try:
            # 生成或使用现有的对话ID
            if not conversation_id:
                conversation_id = self._generate_conversation_id()
            
            # 获取对话历史
            conversation_key = f"{user_id}_{conversation_id}"
            history = self.conversation_history.get(conversation_key, [])
            
            # 构建RAG上下文
            context = self._build_rag_context(query)
            
            # 构建聊天提示词
            messages = self._build_chat_prompt(query, context, history)
            
            # 调用LLM
            if stream:
                # TODO: 实现流式响应
                response = await self._generate_streaming_response(messages)
                return {
                    "conversation_id": conversation_id,
                    "response": response,
                    "context_used": len(context) > 50,
                    "stream": True
                }
            else:
                think_response, json_response = self.llm.call_llm(messages=messages)
                
                # 使用DeepSeek处理器提取和清理答案
                answer = DeepSeekProcessor.extract_answer(think_response, json_response)
                
                # 验证答案质量
                if not DeepSeekProcessor.validate_answer(answer):
                    answer = "抱歉，我暂时无法为您提供满意的回答。请尝试重新表述您的问题。"
                else:
                    # 格式化金融相关答案
                    answer = DeepSeekProcessor.format_financial_answer(answer, len(context) > 50)
                
                # 更新对话历史
                history.append({"role": "user", "content": query})
                history.append({"role": "assistant", "content": answer})
                self.conversation_history[conversation_key] = history
                
                return {
                    "conversation_id": conversation_id,
                    "answer": answer,
                    "context_used": len(context) > 50,
                    "stream": False,
                    "message_id": f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(answer) % 10000}"
                }
                
        except UnicodeEncodeError as e:
            task_logger.error(f"Unicode编码错误: {str(e)}")
            return {
                "answer": "抱歉，回答内容包含特殊字符，已为您重新处理。请重试您的问题。",
                "conversation_id": conversation_id or "unknown",
                "context_used": False,
                "stream": False,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            task_logger.error(f"聊天处理失败: {str(e)}")
            error_msg = "处理请求时出现问题，请重试。"
            if "BadRequestError" in str(e):
                error_msg = "LLM服务请求失败，请检查网络连接。"
            elif "timeout" in str(e).lower():
                error_msg = "请求超时，请重试。"
            
            return {
                "error": error_msg,
                "conversation_id": conversation_id or "unknown",
                "timestamp": datetime.now().isoformat()
            }
    
    async def _generate_streaming_response(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        """生成流式响应（占位符，需要根据具体LLM实现）"""
        # 这里需要根据具体的LLM服务实现流式响应
        # 暂时返回普通响应
        think_response, json_response = self.llm.call_llm(messages=messages)
        
        if json_response and "content" in json_response:
            answer = json_response["content"]
        else:
            answer = think_response if think_response else "抱歉，我无法处理您的请求。"
        
        # 模拟流式输出
        words = answer.split()
        for i, word in enumerate(words):
            if i == 0:
                yield word
            else:
                yield f" {word}"
    
    def get_conversation_history(
        self, 
        conversation_id: str, 
        user_id: str = "default_user",
        limit: int = 20
    ) -> List[Dict]:
        """获取对话历史"""
        conversation_key = f"{user_id}_{conversation_id}"
        history = self.conversation_history.get(conversation_key, [])
        
        # 转换为消息格式
        messages = []
        for i in range(0, len(history), 2):
            if i + 1 < len(history):
                messages.append({
                    "id": f"msg_{i//2}",
                    "query": history[i]["content"],
                    "answer": history[i + 1]["content"],
                    "created_at": datetime.now().isoformat()  # 实际应该存储真实时间
                })
        
        return messages[-limit:]
    
    def clear_conversation(self, conversation_id: str, user_id: str = "default_user") -> bool:
        """清除对话历史"""
        conversation_key = f"{user_id}_{conversation_id}"
        if conversation_key in self.conversation_history:
            del self.conversation_history[conversation_key]
            return True
        return False
    
    def feedback_message(
        self, 
        message_id: str, 
        rating: str, 
        content: Optional[str] = None
    ) -> Dict:
        """处理消息反馈"""
        # 这里可以记录用户反馈，用于改进服务
        task_logger.info(f"收到消息反馈: {message_id}, 评分: {rating}, 内容: {content}")
        
        return {
            "message": "反馈已记录",
            "message_id": message_id,
            "rating": rating
        }
    
    def get_service_stats(self) -> Dict:
        """获取服务统计信息"""
        total_conversations = len(self.conversation_history)
        total_messages = sum(len(hist) for hist in self.conversation_history.values())
        vector_stats = self.doc_manager.vector_service.get_stats()
        
        return {
            "chat_service": {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "active_conversations": total_conversations
            },
            "vector_database": vector_stats
        }


# 全局聊天服务实例
chat_service = LocalChatService() 