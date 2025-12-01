#!/usr/bin/env python3
"""
FAISS向量数据库替换功能测试脚本

用于验证FAISS替换Dify后的各项功能是否正常工作
"""

import asyncio
import json
import time
from datetime import datetime
from typing import List, Dict

from logger import task_logger
from services.vector_service import VectorService, DocumentManager
from services.chat_service import LocalChatService


class FaissReplacementTester:
    """FAISS替换功能测试器"""
    
    def __init__(self):
        self.vector_service = VectorService()
        self.doc_manager = DocumentManager()
        self.chat_service = LocalChatService()
        self.test_results = []
    
    def add_test_result(self, test_name: str, success: bool, details: str = "", duration: float = 0):
        """添加测试结果"""
        self.test_results.append({
            "test_name": test_name,
            "success": success,
            "details": details,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        })
    
    async def test_vector_service_basic(self) -> bool:
        """测试向量服务基础功能"""
        print("🔍 测试向量服务基础功能...")
        start_time = time.time()
        
        try:
            # 测试添加文档
            test_doc_id = "test_doc_001"
            test_content = "这是一个测试文档，用于验证向量数据库的基础功能。包含金融、投资、股票等关键词。"
            test_metadata = {
                "type": "测试文章",
                "date": time.time(),
                "title": "测试文档标题"
            }
            
            # 添加文档
            success = self.doc_manager.add_document(
                doc_id=test_doc_id,
                content=test_content,
                metadata=test_metadata
            )
            
            if not success:
                raise Exception("添加文档失败")
            
            # 测试检索
            results = self.doc_manager.search_related_posts("金融投资", k=3)
            
            if not results:
                raise Exception("检索结果为空")
            
            # 验证结果格式
            for result in results:
                required_keys = ["doc_id", "score", "content", "metadata"]
                if not all(key in result for key in required_keys):
                    raise Exception(f"检索结果格式不正确: {result.keys()}")
            
            # 清理测试数据
            self.doc_manager.remove_document(test_doc_id)
            
            duration = time.time() - start_time
            self.add_test_result("向量服务基础功能", True, f"成功添加和检索文档，返回{len(results)}个结果", duration)
            print(f"  ✅ 向量服务基础功能测试通过 ({duration:.2f}s)")
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("向量服务基础功能", False, str(e), duration)
            print(f"  ❌ 向量服务基础功能测试失败: {str(e)}")
            return False
    
    async def test_document_manager(self) -> bool:
        """测试文档管理器"""
        print("📚 测试文档管理器...")
        start_time = time.time()
        
        try:
            # 测试批量添加
            test_docs = [
                {
                    "doc_id": f"test_batch_{i}",
                    "content": f"批量测试文档{i}，包含不同的金融主题和投资策略分析。",
                    "metadata": {
                        "type": "批量测试",
                        "date": time.time(),
                        "batch_id": i
                    }
                }
                for i in range(5)
            ]
            
            # 批量添加
            success_count = 0
            for doc in test_docs:
                if self.doc_manager.add_document(**doc, save_immediately=False):
                    success_count += 1
            
            # 保存索引
            self.doc_manager.vector_service.save_index()
            
            if success_count != len(test_docs):
                raise Exception(f"批量添加失败，成功{success_count}/{len(test_docs)}")
            
            # 测试文档存在检查
            for doc in test_docs:
                if not self.doc_manager.document_exists(doc["doc_id"]):
                    raise Exception(f"文档不存在: {doc['doc_id']}")
            
            # 测试检索
            results = self.doc_manager.search_related_posts("投资策略", k=3)
            if len(results) < 3:
                raise Exception(f"检索结果不足，期望3个，实际{len(results)}个")
            
            # 清理测试数据
            for doc in test_docs:
                self.doc_manager.remove_document(doc["doc_id"])
            
            duration = time.time() - start_time
            self.add_test_result("文档管理器", True, f"成功处理{len(test_docs)}个文档", duration)
            print(f"  ✅ 文档管理器测试通过 ({duration:.2f}s)")
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("文档管理器", False, str(e), duration)
            print(f"  ❌ 文档管理器测试失败: {str(e)}")
            return False
    
    async def test_chat_service(self) -> bool:
        """测试聊天服务"""
        print("💬 测试聊天服务...")
        start_time = time.time()
        
        try:
            # 添加一些测试数据供聊天使用
            test_financial_docs = [
                {
                    "doc_id": "fin_doc_1",
                    "content": "今日A股市场表现强劲，上证指数上涨2.5%，深证成指上涨3.1%。科技股领涨，新能源板块表现突出。",
                    "metadata": {"type": "早间必读", "date": time.time()}
                },
                {
                    "doc_id": "fin_doc_2", 
                    "content": "美联储决议维持利率不变，市场对此反应积极。全球股市普遍上涨，投资者信心回升。",
                    "metadata": {"type": "逻辑复盘", "date": time.time()}
                }
            ]
            
            # 添加测试文档
            for doc in test_financial_docs:
                self.doc_manager.add_document(**doc)
            
            # 测试聊天功能
            test_query = "今天股市行情如何？"
            chat_result = await self.chat_service.chat(
                query=test_query,
                user_id="test_user"
            )
            
            # 验证聊天结果
            required_keys = ["conversation_id", "answer"]
            if not all(key in chat_result for key in required_keys):
                raise Exception(f"聊天结果格式不正确: {chat_result.keys()}")
            
            if not chat_result["answer"]:
                raise Exception("聊天回答为空")
            
            # 测试对话历史
            conversation_id = chat_result["conversation_id"]
            history = self.chat_service.get_conversation_history(conversation_id, "test_user")
            
            if not history:
                raise Exception("对话历史为空")
            
            # 清理测试数据
            for doc in test_financial_docs:
                self.doc_manager.remove_document(doc["doc_id"])
            
            self.chat_service.clear_conversation(conversation_id, "test_user")
            
            duration = time.time() - start_time
            self.add_test_result("聊天服务", True, f"成功处理查询并生成回答", duration)
            print(f"  ✅ 聊天服务测试通过 ({duration:.2f}s)")
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("聊天服务", False, str(e), duration)
            print(f"  ❌ 聊天服务测试失败: {str(e)}")
            return False
    
    async def test_performance(self) -> bool:
        """测试性能"""
        print("⚡ 测试性能...")
        start_time = time.time()
        
        try:
            # 准备测试数据
            num_docs = 100
            test_docs = []
            
            print(f"  📝 准备{num_docs}个测试文档...")
            for i in range(num_docs):
                test_docs.append({
                    "doc_id": f"perf_test_{i}",
                    "content": f"性能测试文档{i}。这是关于金融市场分析的第{i}篇文章，包含股票、基金、期货等投资工具的分析内容。",
                    "metadata": {
                        "type": "性能测试",
                        "date": time.time(),
                        "doc_number": i
                    }
                })
            
            # 测试批量添加性能
            batch_start = time.time()
            for doc in test_docs:
                self.doc_manager.add_document(**doc, save_immediately=False)
            self.doc_manager.vector_service.save_index()
            batch_duration = time.time() - batch_start
            
            print(f"  📊 批量添加{num_docs}个文档耗时: {batch_duration:.2f}s")
            
            # 测试检索性能
            search_queries = ["市场分析", "投资策略", "股票基金", "金融工具", "期货交易"]
            search_times = []
            
            for query in search_queries:
                search_start = time.time()
                results = self.doc_manager.search_related_posts(query, k=10)
                search_time = time.time() - search_start
                search_times.append(search_time)
                
                if len(results) == 0:
                    raise Exception(f"查询'{query}'无结果")
            
            avg_search_time = sum(search_times) / len(search_times)
            print(f"  🔍 平均检索时间: {avg_search_time:.3f}s")
            
            # 性能标准检查
            if batch_duration > 60:  # 批量添加不应超过1分钟
                raise Exception(f"批量添加性能不达标: {batch_duration:.2f}s > 60s")
            
            if avg_search_time > 1.0:  # 平均检索时间不应超过1秒
                raise Exception(f"检索性能不达标: {avg_search_time:.3f}s > 1.0s")
            
            # 清理测试数据
            for doc in test_docs:
                self.doc_manager.remove_document(doc["doc_id"])
            
            duration = time.time() - start_time
            details = f"批量添加{num_docs}文档:{batch_duration:.2f}s, 平均检索:{avg_search_time:.3f}s"
            self.add_test_result("性能测试", True, details, duration)
            print(f"  ✅ 性能测试通过 ({duration:.2f}s)")
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("性能测试", False, str(e), duration)
            print(f"  ❌ 性能测试失败: {str(e)}")
            return False
    
    def print_test_summary(self):
        """打印测试总结"""
        print("\n" + "="*60)
        print("📋 FAISS替换功能测试总结")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"🧪 总测试数: {total_tests}")
        print(f"✅ 通过: {passed_tests}")
        print(f"❌ 失败: {failed_tests}")
        print(f"📊 通过率: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\n📝 详细结果:")
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            duration = f"({result['duration']:.2f}s)" if result['duration'] > 0 else ""
            print(f"  {status} {result['test_name']} {duration}")
            if result["details"]:
                print(f"     {result['details']}")
        
        if failed_tests == 0:
            print("\n🎉 所有测试通过！FAISS替换功能正常工作。")
        else:
            print(f"\n⚠️  有{failed_tests}个测试失败，请检查相关功能。")
        
        print("="*60)
        
        # 输出系统状态
        try:
            stats = self.doc_manager.vector_service.get_stats()
            print(f"\n🔍 当前向量数据库状态:")
            print(f"   📄 文档总数: {stats['total_documents']}")
            print(f"   🧩 分块总数: {stats['total_chunks']}")
            print(f"   💾 索引大小: {stats['index_size']}")
        except:
            print("\n⚠️  无法获取向量数据库状态")


async def main():
    """主测试函数"""
    print("🚀 开始FAISS替换功能测试...")
    print("="*60)
    
    tester = FaissReplacementTester()
    
    # 运行所有测试
    test_functions = [
        tester.test_vector_service_basic,
        tester.test_document_manager,
        tester.test_chat_service,
        tester.test_performance
    ]
    
    for test_func in test_functions:
        try:
            await test_func()
        except Exception as e:
            print(f"  ❌ 测试执行异常: {str(e)}")
            tester.add_test_result(test_func.__name__, False, f"执行异常: {str(e)}")
    
    # 打印总结
    tester.print_test_summary()


if __name__ == "__main__":
    asyncio.run(main()) 