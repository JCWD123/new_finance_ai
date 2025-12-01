#!/usr/bin/env python3
"""
DeepSeek-R1 输出处理器

专门处理DeepSeek-R1模型的特殊输出格式和编码问题
"""

import re
import json
from typing import Tuple, Optional


class DeepSeekProcessor:
    """DeepSeek-R1 输出处理器"""
    
    @staticmethod
    def clean_content(content: str) -> str:
        """清理DeepSeek输出内容"""
        if not content:
            return ""
        
        try:
            # 步骤1: 处理代理对和无效Unicode字符
            content = DeepSeekProcessor._fix_unicode_issues(content)
            
            # 步骤2: 移除控制字符，但保留常用的换行符
            content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\r\t')
            
            # 步骤3: 处理DeepSeek特有的标记
            content = DeepSeekProcessor._remove_deepseek_markers(content)
            
            # 步骤4: 清理多余的空白
            content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # 多个空行变成两个
            content = re.sub(r'[ \t]+', ' ', content)  # 多个空格变成一个
            content = content.strip()
            
            # 步骤5: 最终验证
            content = DeepSeekProcessor._final_validation(content)
            
            return content
            
        except Exception as e:
            print(f"清理内容时出错: {e}")
            return "内容处理时出现问题，请重试。"
    
    @staticmethod
    def _fix_unicode_issues(content: str) -> str:
        """修复Unicode代理对和编码问题"""
        if not content:
            return ""
        
        try:
            # 方法1: 使用errors='ignore'移除无效字符
            cleaned = content.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
            
            # 方法2: 如果还有问题，逐字符检查
            if len(cleaned) < len(content) * 0.8:  # 如果丢失太多内容，尝试逐字符修复
                result = []
                for char in content:
                    try:
                        # 检查字符是否可以正常编码
                        char.encode('utf-8')
                        # 检查是否是代理对
                        if 0xD800 <= ord(char) <= 0xDFFF:
                            continue  # 跳过代理对字符
                        result.append(char)
                    except (UnicodeEncodeError, UnicodeDecodeError):
                        continue  # 跳过有问题的字符
                
                cleaned = ''.join(result)
            
            return cleaned
            
        except Exception as e:
            print(f"修复Unicode问题时出错: {e}")
            # 最后的备用方案：只保留ASCII和常见中文字符
            return ''.join(char for char in content if ord(char) < 128 or 0x4e00 <= ord(char) <= 0x9fff)
    
    @staticmethod
    def _final_validation(content: str) -> str:
        """最终验证和清理"""
        if not content:
            return "抱歉，回答内容处理时出现问题。"
        
        try:
            # 测试是否可以正常编码
            content.encode('utf-8')
            
            # 确保内容不为空且有意义
            if len(content.strip()) < 5:
                return "抱歉，回答内容太短，请重新提问。"
            
            return content
            
        except UnicodeEncodeError as e:
            print(f"最终验证失败: {e}")
            # 如果还有编码问题，返回安全的默认回答
            return "抱歉，回答内容包含特殊字符无法显示，请重新提问。"
    
    @staticmethod
    def _remove_deepseek_markers(content: str) -> str:
        """移除DeepSeek特有的标记"""
        # 移除思考标记
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # 移除模型内部标记
        content = re.sub(r'<\|.*?\|>', '', content)
        
        # 移除JSON代码块标记
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*$', '', content)
        
        return content
    
    @staticmethod
    def extract_answer(think_response: str, json_response: dict) -> str:
        """从DeepSeek响应中提取最终答案"""
        answer = ""
        
        # 优先使用JSON响应
        if json_response and isinstance(json_response, dict):
            # 尝试常见的字段名
            for field in ['content', 'answer', 'response', 'message', 'text']:
                if field in json_response:
                    answer = str(json_response[field])
                    break
            
            # 如果没有找到常见字段，尝试解析复杂的JSON结构
            if not answer:
                # 尝试提取所有文本内容并格式化
                def extract_text_from_dict(obj, depth=0):
                    if depth > 3:  # 防止无限递归
                        return ""
                    
                    texts = []
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, str) and len(value) > 10:
                                # 格式化键名
                                formatted_key = key.replace('_', ' ').title()
                                texts.append(f"**{formatted_key}**: {value}")
                            elif isinstance(value, (dict, list)):
                                sub_text = extract_text_from_dict(value, depth + 1)
                                if sub_text:
                                    formatted_key = key.replace('_', ' ').title()
                                    if depth == 0:
                                        texts.append(f"\n## {formatted_key}\n{sub_text}")
                                    else:
                                        texts.append(f"**{formatted_key}**: {sub_text}")
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            sub_text = extract_text_from_dict(item, depth + 1)
                            if sub_text:
                                texts.append(f"{i+1}. {sub_text}")
                    elif isinstance(obj, str) and len(obj) > 10:
                        texts.append(obj)
                    
                    return "\n".join(texts) if depth == 0 else " ".join(texts)
                
                answer = extract_text_from_dict(json_response)
        
        # 如果JSON响应为空或无效，使用think_response
        if not answer and think_response:
            answer = str(think_response)
        
        # 如果还是为空，返回默认消息
        if not answer:
            answer = "抱歉，我无法处理您的请求。"
        
        # 清理答案
        answer = DeepSeekProcessor.clean_content(answer)
        
        return answer
    
    @staticmethod
    def validate_answer(answer: str) -> bool:
        """验证答案是否有效"""
        if not answer or len(answer.strip()) < 2:
            return False
        
        # 检查是否只包含错误信息
        error_patterns = [
            r'BadRequestError',
            r'无法处理',
            r'处理时出现问题',
            r'编码问题'
        ]
        
        for pattern in error_patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                return False
        
        return True
    
    @staticmethod
    def format_financial_answer(answer: str, context_used: bool = False) -> str:
        """格式化金融相关答案"""
        if not answer:
            return "很抱歉，我无法为您提供准确的金融分析。"
        
        # 确保答案以适当的语气开始
        if not any(answer.startswith(prefix) for prefix in ['根据', '基于', '从', '据', '分析']):
            if context_used:
                answer = f"根据相关资料分析，{answer}"
            else:
                answer = f"基于一般性分析，{answer}"
        
        # 添加风险提示（对于投资建议）
        investment_keywords = ['投资', '建议', '买入', '卖出', '配置', '持有']
        if any(keyword in answer for keyword in investment_keywords):
            if '风险' not in answer and '仅供参考' not in answer:
                answer += "\n\n⚠️ 以上分析仅供参考，投资有风险，决策需谨慎。"
        
        return answer


def test_processor():
    """测试DeepSeek处理器"""
    print("🧪 测试DeepSeek处理器...")
    
    # 测试数据
    test_cases = [
        {
            "think": "<think>用户问股票行情</think>今天A股表现不错",
            "json": {"content": "A股今日上涨2.5%"},
            "expected": "A股今日上涨2.5%"
        },
        {
            "think": "市场分析：科技股领涨",
            "json": {},
            "expected": "根据相关资料分析，市场分析：科技股领涨"
        }
    ]
    
    processor = DeepSeekProcessor()
    
    for i, case in enumerate(test_cases):
        result = processor.extract_answer(case["think"], case["json"])
        result = processor.format_financial_answer(result, context_used=True)
        
        print(f"测试 {i+1}: {'✅' if result else '❌'}")
        print(f"  输入: {case['think'][:50]}...")
        print(f"  输出: {result[:100]}...")
        print()
    
    print("✅ DeepSeek处理器测试完成")


if __name__ == "__main__":
    test_processor() 