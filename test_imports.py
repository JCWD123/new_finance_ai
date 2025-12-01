#!/usr/bin/env python3
"""
快速测试关键导入是否正常工作
"""

print("🧪 测试关键模块导入...")

try:
    import numpy as np
    print(f"✅ NumPy {np.__version__} - 导入成功")
except Exception as e:
    print(f"❌ NumPy导入失败: {e}")

try:
    import faiss
    print("✅ FAISS - 导入成功")
    
    # 测试基本功能
    d = 64
    index = faiss.IndexFlatL2(d)
    print("✅ FAISS基本功能测试成功")
except Exception as e:
    print(f"❌ FAISS导入或测试失败: {e}")

try:
    from sentence_transformers import SentenceTransformer
    print("✅ sentence-transformers - 导入成功")
except Exception as e:
    print(f"❌ sentence-transformers导入失败: {e}")

try:
    from services.vector_service import DocumentManager
    print("✅ DocumentManager - 导入成功")
except Exception as e:
    print(f"❌ DocumentManager导入失败: {e}")

print("\n🎯 如果所有模块都导入成功，现在可以运行:")
print("   python migrate_to_faiss.py --force") 