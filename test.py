# 更新精华分析结果
# from core.posts import PostsProcessor
# import asyncio

# posts_processor = PostsProcessor(type="Essence")
# asyncio.run(posts_processor.extract_posts(limit=None))



"""
OSS图片上传使用示例
"""
import asyncio
from services.oss_uploader import OSSImageUploader
from config.settings import OSS_CONFIG

async def example_upload():
    """上传示例"""
    
    # 初始化上传器
    uploader = OSSImageUploader(
        access_key_id=OSS_CONFIG["access_key_id"],
        access_key_secret=OSS_CONFIG["access_key_secret"],
        endpoint=OSS_CONFIG["endpoint"],
        bucket_name=OSS_CONFIG["bucket_name"],
        base_path=OSS_CONFIG["base_path"]
    )
    
    # # 示例1: 上传本地文件
    # with open("example.jpg", "rb") as f:
    #     file_content = f.read()
    
    # result = uploader.upload_image(
    #     file_content=file_content,
    #     filename="example.jpg",
    #     custom_name="test_image",
    #     subfolder="examples",
    #     compress=True
    # )
    
    # if result["success"]:
    #     print(f"上传成功!")
    #     print(f"URL: {result['url']}")
    #     print(f"对象键: {result['object_key']}")
    #     print(f"文件大小: {result['size']} bytes")
    # else:
    #     print(f"上传失败: {result['error']}")
    
    # 示例2: 从URL上传（直接放在images目录下）
    url_result = uploader.upload_from_url(
        image_url="https://private.red-ring.cn/6I0efhmV90hT_20250222072213.png-bigsize?e=1748654406&token=Lz2VxvvXxFZUQuBqe9GizzLJKCKTJl4br1cjFZzo:A178TMRX3mm2MS0pWV-2DpQO320=",
        custom_name="url_image",
        # subfolder="from_url",  # 注释掉子文件夹
        compress=False,
        make_public=False
    )
    
    if url_result["success"]:
        print(f"URL上传成功: {url_result['url']}")
        print(f"对象键: {url_result['object_key']}")
        print(f"文件大小: {url_result['size']} bytes")
        
        # 如果需要更长期的URL，可以重新生成签名URL
        long_term_url = uploader.get_signed_url(url_result['object_key'], expires=7*24*3600)  # 7天有效期
        print(f"长期签名URL: {long_term_url}")
        
    else:
        print(f"URL上传失败: {url_result['error']}")

if __name__ == "__main__":
    asyncio.run(example_upload())