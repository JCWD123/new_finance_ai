#!/usr/bin/env python3
"""
聊天界面启动脚本

专门为DeepSeek-R1模型优化的聊天界面
"""

import os
import sys
import asyncio
from datetime import datetime

# 设置环境变量
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "true"

# 确保在正确的目录
if not os.path.exists('services'):
    print("❌ 请在项目根目录运行此脚本")
    sys.exit(1)

def test_environment():
    """测试环境是否正确设置"""
    print("🔍 检查环境...")
    
    try:
        import numpy as np
        print(f"✅ NumPy {np.__version__}")
    except Exception as e:
        print(f"❌ NumPy导入失败: {e}")
        return False
    
    try:
        import faiss
        print("✅ FAISS")
    except Exception as e:
        print(f"❌ FAISS导入失败: {e}")
        return False
    
    try:
        from services.vector_service import DocumentManager
        from services.chat_service import LocalChatService
        print("✅ 聊天服务")
    except Exception as e:
        print(f"❌ 聊天服务导入失败: {e}")
        return False
    
    return True

async def simple_chat():
    """简化的聊天界面"""
    print("="*60)
    print("🤖 金融学长 AI 聊天助手 (DeepSeek-R1)")
    print("="*60)
    print("💡 输入问题开始对话，输入 'quit' 退出")
    print("💡 支持：股市分析、投资建议、市场行情等金融话题")
    print("="*60)
    
    try:
        from services.chat_service import LocalChatService
        from services.vector_service import DocumentManager
        
        chat_service = LocalChatService()
        doc_manager = DocumentManager()
        
        # 检查数据状态
        stats = doc_manager.vector_service.get_stats()
        doc_count = stats.get("total_documents", 0)
        
        if doc_count == 0:
            print("⚠️  向量数据库为空，添加示例数据...")
            # 添加一些示例数据
            sample_docs = [
                {
                    "doc_id": "sample_market",
                    "content": "今日A股市场表现强劲，上证指数上涨2.5%，深证成指上涨3.1%。科技股和新能源板块领涨，市场情绪乐观。",
                    "metadata": {"type": "早间必读", "title": "A股强势表现"}
                },
                {
                    "doc_id": "sample_strategy",
                    "content": "投资策略建议：当前市场环境下建议均衡配置，重点关注科技创新、新能源和消费升级三大主线。风险控制方面，建议单一股票仓位不超过总资产的10%。",
                    "metadata": {"type": "投资策略", "title": "均衡配置建议"}
                }
            ]
            
            for doc in sample_docs:
                doc_manager.add_document(**doc)
            print("✅ 示例数据添加完成")
        else:
            print(f"✅ 向量数据库包含 {doc_count} 个文档")
        
        conversation_id = None
        user_id = "simple_chat_user"
        
        while True:
            try:
                # 获取用户输入
                user_input = input("\n💬 您: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q', '退出']:
                    print("👋 感谢使用，再见！")
                    break
                
                # 显示思考状态
                print("🤔 DeepSeek正在思考...")
                
                # 发送消息
                result = await chat_service.chat(
                    query=user_input,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    stream=False
                )
                
                if "error" in result:
                    print(f"❌ 错误: {result['error']}")
                    print("💡 请重试或换个问法")
                else:
                    conversation_id = result["conversation_id"]
                    answer = result.get("answer", "抱歉，我无法回答这个问题。")
                    context_used = result.get("context_used", False)
                    
                    print(f"\n🤖 AI回复:")
                    print("─" * 50)
                    print(answer)
                    print("─" * 50)
                    
                    if context_used:
                        print("📚 回答基于历史文章数据")
                    else:
                        print("💭 回答基于一般知识")
                
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，再见！")
                break
            except Exception as e:
                print(f"❌ 发生错误: {e}")
                print("💡 请重试")
    
    except Exception as e:
        print(f"❌ 聊天服务初始化失败: {e}")
        print("💡 请检查环境配置和依赖安装")

def main():
    """主函数"""
    print("🚀 启动聊天界面...")
    
    # 测试环境
    if not test_environment():
        print("\n❌ 环境检查失败")
        print("💡 请运行以下命令修复：")
        print("   python -m pip install \"numpy>=1.21.0,<2.0.0\"")
        print("   python -m pip install faiss-cpu==1.8.0")
        print("   python -m pip install -r requirements.txt")
        return
    
    print("✅ 环境检查通过")
    
    # 启动聊天
    try:
        asyncio.run(simple_chat())
    except Exception as e:
        print(f"❌ 程序运行失败: {e}")

if __name__ == "__main__":
    main()