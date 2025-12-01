#!/usr/bin/env python3
"""
交互式聊天界面

用法：
python interactive_chat.py
"""

import sys
import os
import asyncio
from datetime import datetime
from typing import Optional

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 设置环境变量修复tokenizers警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"

try:
    from logger import task_logger
except ImportError:
    # 如果导入失败，创建简单的日志器
    import logging
    logging.basicConfig(level=logging.INFO)
    task_logger = logging.getLogger(__name__)

try:
    from services.chat_service import LocalChatService
    from services.vector_service import DocumentManager
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保在项目根目录运行，并且已安装所有依赖")
    sys.exit(1)


class InteractiveChatInterface:
    """交互式聊天界面"""
    
    def __init__(self):
        try:
            self.chat_service = LocalChatService()
            self.doc_manager = DocumentManager()
            self.current_conversation_id = None
            self.user_id = "interactive_user"
            print("✅ 聊天服务初始化成功")
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            sys.exit(1)
    
    def print_banner(self):
        """打印欢迎横幅"""
        print("="*60)
        print("🤖 金融学长 AI 聊天助手")
        print("基于 FAISS 向量数据库的智能问答系统")
        print("="*60)
        print("📝 输入 'help' 查看帮助")
        print("📝 输入 'quit' 或 'exit' 退出")
        print("📝 输入 'stats' 查看系统状态")
        print("📝 输入 'clear' 清除对话历史")
        print("="*60)
    
    def print_help(self):
        """打印帮助信息"""
        print("\n📚 帮助信息:")
        print("🔹 直接输入问题即可开始对话")
        print("🔹 支持的金融话题：股市分析、投资策略、市场行情等")
        print("🔹 系统会基于历史文章提供参考信息")
        print("🔹 可以问类似：'今天股市如何？'、'有什么投资建议？'")
        print("🔹 特殊命令：")
        print("   - help: 显示此帮助")
        print("   - stats: 显示系统统计")
        print("   - clear: 清除当前对话")
        print("   - quit/exit: 退出程序")
        print()
    
    def print_stats(self):
        """打印系统统计"""
        try:
            stats = self.chat_service.get_service_stats()
            print("\n📊 系统统计:")
            print("="*40)
            
            chat_stats = stats.get("chat_service", {})
            print(f"💬 聊天服务:")
            print(f"   对话总数: {chat_stats.get('total_conversations', 0)}")
            print(f"   消息总数: {chat_stats.get('total_messages', 0)}")
            print(f"   活跃对话: {chat_stats.get('active_conversations', 0)}")
            
            vector_stats = stats.get("vector_database", {})
            print(f"🔍 向量数据库:")
            print(f"   文档总数: {vector_stats.get('total_documents', 0)}")
            print(f"   分块总数: {vector_stats.get('total_chunks', 0)}")
            print(f"   索引大小: {vector_stats.get('index_size', 'N/A')}")
            print("="*40)
            
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")
    
    def clear_conversation(self):
        """清除当前对话"""
        if self.current_conversation_id:
            success = self.chat_service.clear_conversation(
                self.current_conversation_id, 
                self.user_id
            )
            if success:
                print("✅ 对话历史已清除")
                self.current_conversation_id = None
            else:
                print("❌ 清除对话失败")
        else:
            print("ℹ️  当前没有活跃对话")
    
    async def send_message(self, message: str) -> bool:
        """发送消息并获取回复"""
        try:
            print("🤔 AI思考中...")
            
            result = await self.chat_service.chat(
                query=message,
                conversation_id=self.current_conversation_id,
                user_id=self.user_id,
                stream=False
            )
            
            if "error" in result:
                print(f"❌ 聊天错误: {result['error']}")
                return False
            
            # 更新对话ID
            self.current_conversation_id = result["conversation_id"]
            
            # 显示回复
            answer = result.get("answer", "抱歉，我无法回答这个问题。")
            context_used = result.get("context_used", False)
            
            print(f"\n🤖 AI回复:")
            print("─" * 50)
            print(answer)
            print("─" * 50)
            
            if context_used:
                print("📚 回答基于历史文章数据")
            else:
                print("💡 回答基于一般知识")
            
            return True
            
        except Exception as e:
            print(f"❌ 发送消息失败: {e}")
            return False
    
    def check_vector_database(self):
        """检查向量数据库状态"""
        try:
            stats = self.doc_manager.vector_service.get_stats()
            doc_count = stats.get("total_documents", 0)
            
            if doc_count == 0:
                print("⚠️  向量数据库为空")
                print("💡 提示：运行 'python migrate_to_faiss.py --force' 来导入数据")
                return False
            else:
                print(f"✅ 向量数据库包含 {doc_count} 个文档")
                return True
                
        except Exception as e:
            print(f"❌ 检查向量数据库失败: {e}")
            return False
    
    async def run(self):
        """运行交互式界面"""
        self.print_banner()
        
        # 检查数据库状态
        if not self.check_vector_database():
            print("\n是否继续？(y/n): ", end="")
            if input().lower().strip() not in ['y', 'yes']:
                print("👋 再见！")
                return
        
        print("\n🚀 聊天已开始，请输入您的问题:")
        
        while True:
            try:
                # 获取用户输入
                user_input = input("\n💬 您: ").strip()
                
                if not user_input:
                    continue
                
                # 处理特殊命令
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 再见！")
                    break
                elif user_input.lower() == 'help':
                    self.print_help()
                    continue
                elif user_input.lower() == 'stats':
                    self.print_stats()
                    continue
                elif user_input.lower() == 'clear':
                    self.clear_conversation()
                    continue
                
                # 发送消息
                success = await self.send_message(user_input)
                if not success:
                    print("💡 请重试或输入 'help' 查看帮助")
                
            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
            except EOFError:
                print("\n\n👋 再见！")
                break
            except Exception as e:
                print(f"❌ 发生错误: {e}")
                print("💡 请重试或输入 'help' 查看帮助")


async def main():
    """主函数"""
    try:
        interface = InteractiveChatInterface()
        await interface.run()
    except Exception as e:
        print(f"❌ 程序运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # 添加一些示例测试数据（如果数据库为空）
    def add_sample_data():
        """添加示例数据"""
        try:
            from services.vector_service import DocumentManager
            doc_manager = DocumentManager()
            
            # 检查是否已有数据
            stats = doc_manager.vector_service.get_stats()
            if stats.get("total_documents", 0) > 0:
                return
            
            print("📝 检测到空数据库，添加示例数据...")
            
            sample_docs = [
                {
                    "doc_id": "sample_market_1",
                    "content": "今日A股市场表现强劲，上证指数上涨2.5%，深证成指上涨3.1%。科技股和新能源板块领涨，投资者情绪乐观。分析师认为，近期政策利好和经济数据改善为市场提供了支撑。",
                    "metadata": {"type": "早间必读", "date": datetime.now().timestamp(), "title": "A股强势上涨"}
                },
                {
                    "doc_id": "sample_strategy_1", 
                    "content": "在当前市场环境下，建议投资者采用均衡配置策略。重点关注：1）科技创新板块，特别是人工智能和新能源；2）消费升级相关行业；3）适度配置防御性资产。风险控制方面，建议控制单一股票仓位不超过10%。",
                    "metadata": {"type": "投资策略", "date": datetime.now().timestamp(), "title": "均衡配置策略"}
                },
                {
                    "doc_id": "sample_fed_1",
                    "content": "美联储最新会议纪要显示，委员们对通胀前景保持谨慎乐观。多数委员认为当前利率水平合适，但强调将密切关注经济数据变化。这一表态缓解了市场对进一步加息的担忧，全球股市普遍反弹。",
                    "metadata": {"type": "逻辑复盘", "date": datetime.now().timestamp(), "title": "美联储政策解读"}
                }
            ]
            
            for doc in sample_docs:
                doc_manager.add_document(**doc)
            
            print("✅ 示例数据添加完成")
            
        except Exception as e:
            print(f"⚠️  添加示例数据失败: {e}")
    
    # 如果数据库为空，添加示例数据
    try:
        add_sample_data()
    except:
        pass
    
    # 运行主程序
    asyncio.run(main()) 