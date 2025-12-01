#!/usr/bin/env python3
"""
测试LLM配置

检查当前使用的模型配置
"""

import os
import sys

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_config():
    """测试配置"""
    print("🔍 检查LLM配置...")
    
    # 检查环境变量
    print(f"环境变量 LLM_MODEL: {os.getenv('LLM_MODEL', '未设置')}")
    print(f"环境变量 LLM_API_KEY: {os.getenv('LLM_API_KEY', '未设置')}")
    print(f"环境变量 LLM_BASE_URL: {os.getenv('LLM_BASE_URL', '未设置')}")
    
    # 导入配置
    try:
        from config.settings import LLM_SETTINGS
        print(f"\n配置文件中的设置:")
        print(f"  model: {LLM_SETTINGS['model']}")
        print(f"  api_key: {LLM_SETTINGS['api_key'][:10]}...")
        print(f"  base_url: {LLM_SETTINGS['base_url']}")
    except Exception as e:
        print(f"❌ 导入配置失败: {e}")
        return
    
    # 测试LLM服务
    try:
        from services.llm import LLMService
        llm = LLMService()
        print(f"\nLLM服务配置:")
        print(f"  使用的模型: {llm.model}")
        print(f"  API Key: {llm.client.api_key[:10] if llm.client.api_key else 'None'}...")
        print(f"  Base URL: {llm.client.base_url}")
    except Exception as e:
        print(f"❌ 创建LLM服务失败: {e}")
        return
    
    # 尝试简单调用
    try:
        print(f"\n🧪 测试LLM调用...")
        messages = [
            {"role": "system", "content": "你是一个AI助手。"},
            {"role": "user", "content": "你好，请简单回复一下。"}
        ]
        
        think_response, json_response = llm.call_llm(messages=messages)
        print(f"✅ LLM调用成功")
        print(f"  think_response: {str(think_response)[:100]}...")
        print(f"  json_response: {json_response}")
        
    except Exception as e:
        print(f"❌ LLM调用失败: {e}")
        if "401" in str(e):
            print("💡 这是认证错误，可能是API密钥或模型权限问题")
        elif "model" in str(e).lower():
            print("💡 这是模型相关错误，请检查模型名称是否正确")

def main():
    """主函数"""
    print("=" * 60)
    print("🔧 LLM配置测试")
    print("=" * 60)
    
    test_config()
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()