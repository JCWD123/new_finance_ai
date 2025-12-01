import re
import json
from typing import List, Dict, Tuple
from services.llm import LLMService
from logger import task_logger

class HTMLContentProcessor:
    """HTML内容处理器"""
    
    def __init__(self):
        self.div_pattern = r'<div[^>]*class="image-container"[^>]*>.*?</div>'
        self.img_pattern = r'<img[^>]*src="([^"]*)"[^>]*>'
        # 初始化LLM服务
        self.llm_service = LLMService()
    
    def extract_div_blocks(self, content: str) -> List[Dict]:
        """提取文章中的div块"""
        try:
            div_blocks = []
            matches = re.finditer(self.div_pattern, content, re.DOTALL)
            
            for i, match in enumerate(matches):
                div_html = match.group(0)
                start_pos = match.start()
                end_pos = match.end()
                
                # 提取图片URL
                img_match = re.search(self.img_pattern, div_html)
                img_url = img_match.group(1) if img_match else None
                
                div_info = {
                    'id': f'div_{i}',
                    'html': div_html,
                    'start_pos': start_pos,
                    'end_pos': end_pos,
                    'img_url': img_url,
                    'placeholder': f'{{{{DIV_BLOCK_{i}}}}}'
                }
                div_blocks.append(div_info)
                
            task_logger.info(f"提取到 {len(div_blocks)} 个div块")
            return div_blocks
            
        except Exception as e:
            task_logger.error(f"提取div块失败: {str(e)}")
            return []
    
    def replace_divs_with_placeholders(self, content: str, div_blocks: List[Dict]) -> str:
        """将div块替换为占位符"""
        try:
            # 从后往前替换，避免位置偏移
            for div_block in reversed(div_blocks):
                start_pos = div_block['start_pos']
                end_pos = div_block['end_pos']
                placeholder = div_block['placeholder']
                
                content = content[:start_pos] + placeholder + content[end_pos:]
            
            return content
            
        except Exception as e:
            task_logger.error(f"替换div块为占位符失败: {str(e)}")
            return content
    
    def analyze_image_content(self, img_url: str) -> Dict:
        """使用LLM服务分析图片内容"""
        try:
            if not img_url:
                return {"error": "图片URL为空", "success": False}
                
            task_logger.info(f"开始分析图片内容: {img_url}")
            
            # 构建图片分析的消息
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的图片分析助手。请仔细分析图片内容，提取其中的关键信息，特别关注财经、数据、图表等相关内容。请以JSON格式返回分析结果。"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请分析这张图片的内容，提取关键信息。如果是图表，请描述数据趋势；如果是文本，请总结要点；如果是其他内容，请描述主要元素。请以JSON格式返回，包含以下字段：{'content_type': '图片类型', 'key_points': ['关键点1', '关键点2'], 'summary': '总结描述', 'data_insights': '数据洞察（如适用）'}"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": img_url
                            }
                        }
                    ]
                }
            ]
            
            # 使用LLM服务的统一调用方法
            think_response, json_response = self.llm_service.call_llm(
                messages=messages,
                max_retries=3,
                timeout=(30, 60)  # 图片分析可能需要更长时间
            )
            
            if json_response == "BadRequestError":
                return {
                    'img_url': img_url,
                    'error': 'LLM API请求错误',
                    'success': False
                }
            
            if isinstance(json_response, dict) and json_response:
                task_logger.info(f"图片内容分析完成: {img_url}")
                return {
                    'img_url': img_url,
                    'analysis_result': json_response,
                    'analysis_text': json_response.get('summary', ''),
                    'content_type': json_response.get('content_type', ''),
                    'key_points': json_response.get('key_points', []),
                    'data_insights': json_response.get('data_insights', ''),
                    'think_response': think_response,
                    'success': True
                }
            else:
                return {
                    'img_url': img_url,
                    'error': 'LLM返回格式错误或为空',
                    'raw_response': json_response,
                    'success': False
                }
            
        except Exception as e:
            task_logger.error(f"图片内容分析失败: {str(e)}")
            return {
                'img_url': img_url,
                'error': str(e),
                'success': False
            }
    
    async def process_div_blocks(self, div_blocks: List[Dict]) -> List[Dict]:
        """处理div块，分析图片内容"""
        try:
            processed_blocks = []
            
            for div_block in div_blocks:
                if div_block['img_url']:
                    # 分析图片内容（同步调用，因为LLM服务是同步的）
                    img_analysis = self.analyze_image_content(div_block['img_url'])
                    div_block['img_analysis'] = img_analysis
                else:
                    div_block['img_analysis'] = {"error": "未找到图片URL", "success": False}
                
                processed_blocks.append(div_block)
            
            return processed_blocks
            
        except Exception as e:
            task_logger.error(f"处理div块失败: {str(e)}")
            return div_blocks
    
    def restore_processed_divs(self, content: str, processed_blocks: List[Dict]) -> str:
        """将处理后的div块还原到原文中"""
        try:
            for div_block in processed_blocks:
                placeholder = div_block['placeholder']
                
                # 构建新的div内容（包含图片分析结果）
                original_html = div_block['html']
                img_analysis = div_block.get('img_analysis', {})
                
                # 添加图片分析结果作为注释
                if img_analysis.get('success'):
                    analysis_result = img_analysis.get('analysis_result', {})
                    summary = analysis_result.get('summary', img_analysis.get('analysis_text', ''))
                    content_type = analysis_result.get('content_type', '')
                    key_points = analysis_result.get('key_points', [])
                    
                    # 构建详细的分析注释
                    analysis_parts = []
                    if content_type:
                        analysis_parts.append(f"类型: {content_type}")
                    if summary:
                        analysis_parts.append(f"摘要: {summary}")
                    if key_points:
                        key_points_str = "; ".join(key_points)
                        analysis_parts.append(f"关键点: {key_points_str}")
                    
                    analysis_text = " | ".join(analysis_parts)
                    analysis_comment = f"<!-- 图片分析结果: {analysis_text} -->"
                    new_html = f"{analysis_comment}\n{original_html}"
                else:
                    error_msg = img_analysis.get('error', '图片分析失败')
                    error_comment = f"<!-- 图片分析错误: {error_msg} -->"
                    new_html = f"{error_comment}\n{original_html}"
                
                # 替换占位符
                content = content.replace(placeholder, new_html)
            
            return content
            
        except Exception as e:
            task_logger.error(f"还原div块失败: {str(e)}")
            return content
    
    async def process_article_content(self, content: str) -> Tuple[str, List[Dict]]:
        """处理文章内容中的div块"""
        try:
            task_logger.info("开始处理文章中的div块")
            
            # 1. 提取div块
            div_blocks = self.extract_div_blocks(content)
            
            if not div_blocks:
                task_logger.info("未找到div块，跳过处理")
                return content, []
            
            # 2. 替换为占位符
            content_with_placeholders = self.replace_divs_with_placeholders(content, div_blocks)
            
            # 3. 处理div块（分析图片）
            processed_blocks = await self.process_div_blocks(div_blocks)
            
            # 4. 还原到原文
            final_content = self.restore_processed_divs(content_with_placeholders, processed_blocks)
            
            task_logger.info("div块处理完成")
            return final_content, processed_blocks
            
        except Exception as e:
            task_logger.error(f"处理文章内容失败: {str(e)}")
            return content, [] 