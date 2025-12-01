#!/usr/bin/env python3
"""
测试Unicode编码问题修复

专门测试DeepSeek-R1模型可能产生的编码问题
"""

import os
import sys

# 设置环境变量
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from services.deepseek_processor import DeepSeekProcessor

def test_unicode_issues():
    """测试各种Unicode问题"""
    print("🧪 测试Unicode编码问题修复...")
    
    # 测试用例：包含可能的问题字符
    test_cases = [
        {
            "name": "正常中文内容",
            "content": "今天A股市场表现强劲，上证指数上涨2.5%。",
            "expected": True
        },
        {
            "name": "包含代理对字符",
            "content": "市场分析\udce6\udcb5\udcb7\udcb8今天表现不错",
            "expected": True
        },
        {
            "name": "混合编码问题",
            "content": "投资建议：\udce6\udcb5\udcb7科技股值得关注",
            "expected": True
        },
        {
            "name": "DeepSeek标记",
            "content": "<think>用户问股票</think>A股今日表现良好",
            "expected": True
        },
        {
            "name": "JSON代码块",
            "content": "```json\n{\"content\": \"市场分析\"}\n```",
            "expected": True
        },
        {
            "name": "空内容",
            "content": "",
            "expected": False
        }
    ]
    
    processor = DeepSeekProcessor()
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {case['name']}")
        print(f"  原始内容: {repr(case['content'])}")
        
        try:
            # 清理内容
            cleaned = processor.clean_content(case['content'])
            print(f"  清理后: {repr(cleaned)}")
            
            # 验证是否可以正常编码
            cleaned.encode('utf-8')
            
            # 检查结果
            is_valid = len(cleaned.strip()) > 0 if case['expected'] else len(cleaned.strip()) == 0
            
            if is_valid:
                print(f"  结果: ✅ 通过")
            else:
                print(f"  结果: ❌ 失败 - 预期{'有内容' if case['expected'] else '无内容'}")
                
        except UnicodeEncodeError as e:
            print(f"  结果: ❌ Unicode编码错误: {e}")
        except Exception as e:
            print(f"  结果: ❌ 其他错误: {e}")

def test_real_deepseek_response():
    """测试模拟的DeepSeek响应"""
    print("\n🧪 测试模拟DeepSeek响应...")
    
    # 模拟可能出现问题的DeepSeek响应
    mock_responses = [
        {
            "think_response": "用户询问股票行情\udce6\udcb5",
            "json_response": {"content": "A股今日上涨2.5%\udce6\udcb5\udcb7"}
        },
        {
            "think_response": "<think>分析市场</think>科技股领涨",
            "json_response": {}
        },
        {
            "think_response": None,
            "json_response": {"content": "```json\n投资建议\n```"}
        }
    ]
    
    processor = DeepSeekProcessor()
    
    for i, response in enumerate(mock_responses, 1):
        print(f"\n模拟响应 {i}:")
        print(f"  think_response: {repr(response['think_response'])}")
        print(f"  json_response: {response['json_response']}")
        
        try:
            # 提取答案
            answer = processor.extract_answer(
                response['think_response'], 
                response['json_response']
            )
            
            # 验证答案
            is_valid = processor.validate_answer(answer)
            
            # 格式化答案
            formatted = processor.format_financial_answer(answer, context_used=True)
            
            print(f"  提取的答案: {repr(answer)}")
            print(f"  答案有效性: {'✅' if is_valid else '❌'}")
            print(f"  格式化后: {formatted[:100]}...")
            
            # 测试编码
            formatted.encode('utf-8')
            print(f"  编码测试: ✅ 通过")
            
        except Exception as e:
            print(f"  处理失败: ❌ {e}")

def main():
    """主测试函数"""
    print("=" * 60)
    print("🔧 Unicode编码问题修复测试")
    print("=" * 60)
    
    test_unicode_issues()
    test_real_deepseek_response()
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()