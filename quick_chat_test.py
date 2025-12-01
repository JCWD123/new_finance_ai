#!/usr/bin/env python3
"""
快速聊天测试脚本

简单测试FAISS向量数据库和聊天功能
"""

import sys
import os
import asyncio

# 确保在正确的目录
if not os.path.exists('services'):
    print("❌ 请在项目根目录运行此脚本")
    sys.exit(1)

def test_imports():
    """测试关键模块导入"""
    print("🧪 测试模块导入...")
    
    try:
        import numpy as np
        print(f"✅ NumPy {np.__version__}")
    except Exception as e:
        print(f"❌ NumPy: {e}")
        return False
    
    try:
        import faiss
        print("✅ FAISS")
    except Exception as e:
        print(f"❌ FAISS: {e}")
        return False
    
    try:
        from sentence_transformers import SentenceTransformer
        print("✅ sentence-transformers")
    except Exception as e:
        print(f"❌ sentence-transformers: {e}")
        return False
    
    return True

def test_vector_service():
    """测试向量服务基本功能"""
    print("\n🔍 测试向量服务...")
    
    try:
        from services.vector_service import VectorService, DocumentManager
        
        # 创建服务实例
        vector_service = VectorService()
        doc_manager = DocumentManager()
        
        print("✅ 向量服务初始化成功")
        
        # 添加测试文档
        test_doc = {
            "doc_id": "quick_test_1",
            "content": "这是一个测试文档，包含金融市场分析内容。",
            "metadata": {"type": "测试", "title": "快速测试"}
        }
        
        success = doc_manager.add_document(**test_doc)
        if success:
            print("✅ 文档添加成功")
        else:
            print("❌ 文档添加失败")
            return False
        
        # 测试搜索
        results = doc_manager.search_related_posts("金融市场", k=1)
        if results:
            print(f"✅ 搜索成功，找到 {len(results)} 个结果")
        else:
            print("⚠️  搜索无结果")
        
        # 清理测试数据
        doc_manager.remove_document("quick_test_1")
        
        return True
        
    except Exception as e:
        print(f"❌ 向量服务测试失败: {e}")
        return False

async def test_chat_service():
    """测试聊天服务"""
    print("\n💬 测试聊天服务...")
    
    try:
        from services.chat_service import LocalChatService
        
        chat_service = LocalChatService()
        print("✅ 聊天服务初始化成功")
        
        # 添加测试数据
        from services.vector_service import DocumentManager
        doc_manager = DocumentManager()
        
        test_docs = [
            {
                "doc_id": "chat_test_1",
                "content": "A股今日表现强劲，上证指数上涨2.5%，科技股领涨。",
                "metadata": {"type": "早间必读"}
            },
            {
                "doc_id": "chat_test_2",
                "content": "投资建议：当前市场建议均衡配置，重点关注科技和新能源板块。",
                "metadata": {"type": "投资策略"}
            }
        ]
        
        for doc in test_docs:
            doc_manager.add_document(**doc)
        
        # 测试聊天
        result = await chat_service.chat(
            query="今天股市怎么样？",
            user_id="test_user"
        )
        
        if "error" not in result:
            print("✅ 聊天测试成功")
            print(f"📝 回答: {result.get('answer', '')[:100]}...")
        else:
            print(f"❌ 聊天测试失败: {result['error']}")
            return False
        
        # 清理测试数据
        for doc in test_docs:
            doc_manager.remove_document(doc["doc_id"])
        
        return True
        
    except Exception as e:
        print(f"❌ 聊天服务测试失败: {e}")
        return False

async def interactive_chat():
    """简单的交互式聊天"""
    print("\n🚀 启动交互式聊天...")
    print("输入 'quit' 退出")
    
    try:
        from services.chat_service import LocalChatService
        from services.vector_service import DocumentManager
        
        chat_service = LocalChatService()
        doc_manager = DocumentManager()
        
        # 检查数据库状态
        stats = doc_manager.vector_service.get_stats()
        doc_count = stats.get("total_documents", 0)
        
        if doc_count == 0:
            print("⚠️  向量数据库为空，添加示例数据...")
            sample_docs = [
                {
                    "doc_id": "sample_1",
                    "content": "今日A股市场表现强劲，上证指数上涨2.5%，深证成指上涨3.1%。科技股领涨，新能源板块表现突出。",
                    "metadata": {"type": "早间必读", "title": "A股强势上涨"}
                },
                {
                    "doc_id": "sample_2",
                    "content": "投资策略建议：当前建议均衡配置，重点关注科技创新和消费升级板块。建议控制单一股票仓位不超过10%。",
                    "metadata": {"type": "投资策略", "title": "均衡配置策略"}
                }
            ]
            
            for doc in sample_docs:
                doc_manager.add_document(**doc)
            print("✅ 示例数据添加完成")
        else:
            print(f"✅ 向量数据库包含 {doc_count} 个文档")
        
        conversation_id = None
        
        while True:
            user_input = input("\n💬 您: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 再见！")
                break
            
            if not user_input:
                continue
            
            print("🤔 思考中...")
            
            result = await chat_service.chat(
                query=user_input,
                conversation_id=conversation_id,
                user_id="quick_test_user"
            )
            
            if "error" in result:
                print(f"❌ 错误: {result['error']}")
            else:
                conversation_id = result["conversation_id"]
                answer = result.get("answer", "抱歉，我无法回答这个问题。")
                print(f"\n🤖 AI: {answer}")
                
                if result.get("context_used", False):
                    print("📚 (基于历史文章)")
    
    except Exception as e:
        print(f"❌ 交互式聊天失败: {e}")

async def main():
    """主函数"""
    print("🚀 快速聊天测试脚本")
    print("="*50)
    
    # 测试导入
    if not test_imports():
        print("\n❌ 模块导入失败，请先修复环境")
        print("运行: python fix_environment.py")
        return
    
    # 测试向量服务
    if not test_vector_service():
        print("\n❌ 向量服务测试失败")
        return
    
    # 测试聊天服务
    if not await test_chat_service():
        print("\n❌ 聊天服务测试失败")
        return
    
    print("\n✅ 所有测试通过！")
    
    # 询问是否进入交互模式
    print("\n是否启动交互式聊天？ (y/n): ", end="")
    choice = input().lower().strip()
    
    if choice in ['y', 'yes']:
        await interactive_chat()
    else:
        print("👋 测试完成！")

if __name__ == "__main__":
    asyncio.run(main()) 