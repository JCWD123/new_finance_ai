import os
import uuid
from datetime import datetime
from typing import Optional, Tuple, Union
import oss2
from oss2.exceptions import OssError
import mimetypes
from PIL import Image
import io

from logger import setup_logger

# 设置日志
oss_logger = setup_logger("oss", "oss.log")

class OSSImageUploader:
    """阿里云OSS图片上传服务"""
    
    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        endpoint: str,
        bucket_name: str,
        base_path: str = "images"
    ):
        """
        初始化OSS上传器
        
        Args:
            access_key_id: 阿里云AccessKey ID
            access_key_secret: 阿里云AccessKey Secret
            endpoint: OSS服务端点
            bucket_name: OSS存储桶名称
            base_path: 文件存储的基础路径
        """
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.base_path = base_path.strip('/')
        
        # 初始化OSS认证和存储桶
        try:
            auth = oss2.Auth(access_key_id, access_key_secret)
            self.bucket = oss2.Bucket(auth, endpoint, bucket_name)
            oss_logger.info(f"OSS连接初始化成功 - Bucket: {bucket_name}")
        except Exception as e:
            oss_logger.error(f"OSS连接初始化失败: {str(e)}")
            raise
    
    def _generate_filename(self, original_filename: str, custom_name: Optional[str] = None) -> str:
        """
        生成唯一的文件名
        
        Args:
            original_filename: 原始文件名
            custom_name: 自定义文件名前缀
            
        Returns:
            生成的唯一文件名
        """
        # 获取文件扩展名
        _, ext = os.path.splitext(original_filename)
        if not ext:
            ext = '.jpg'  # 默认扩展名
        
        # 生成时间戳和UUID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        if custom_name:
            filename = f"{custom_name}_{timestamp}_{unique_id}{ext}"
        else:
            filename = f"img_{timestamp}_{unique_id}{ext}"
        
        return filename
    
    def _get_object_key(self, filename: str, subfolder: Optional[str] = None) -> str:
        """
        生成OSS对象键
        
        Args:
            filename: 文件名
            subfolder: 子文件夹（可选，如果不需要可以不传）
            
        Returns:
            完整的对象键路径
        """
        # 简化路径结构，直接放在base_path下
        if subfolder:
            object_key = f"{self.base_path}/{subfolder}/{filename}"
        else:
            object_key = f"{self.base_path}/{filename}"
        
        return object_key
    
    def _validate_image(self, file_content: bytes) -> Tuple[bool, str]:
        """
        验证图片文件
        
        Args:
            file_content: 文件内容
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            # 检查文件大小 (最大10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if len(file_content) > max_size:
                return False, f"文件大小超过限制 ({max_size / 1024 / 1024}MB)"
            
            # 验证是否为有效图片
            image = Image.open(io.BytesIO(file_content))
            image.verify()
            
            # 检查图片格式
            allowed_formats = ['JPEG', 'PNG', 'GIF', 'BMP', 'WEBP']
            if image.format not in allowed_formats:
                return False, f"不支持的图片格式: {image.format}"
            
            return True, ""
            
        except Exception as e:
            return False, f"图片验证失败: {str(e)}"
    
    def _compress_image(self, file_content: bytes, max_width: int = 1920, quality: int = 85) -> bytes:
        """
        压缩图片
        
        Args:
            file_content: 原始文件内容
            max_width: 最大宽度
            quality: 压缩质量 (1-100)
            
        Returns:
            压缩后的文件内容
        """
        try:
            image = Image.open(io.BytesIO(file_content))
            
            # 如果图片宽度超过最大宽度，进行等比缩放
            if image.width > max_width:
                ratio = max_width / image.width
                new_height = int(image.height * ratio)
                image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # 转换为RGB模式（如果需要）
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')
            
            # 保存压缩后的图片
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue()
            
        except Exception as e:
            oss_logger.warning(f"图片压缩失败，使用原图: {str(e)}")
            return file_content
    
    def upload_image(
        self,
        file_content: bytes,
        filename: str,
        custom_name: Optional[str] = None,
        subfolder: Optional[str] = None,
        compress: bool = True,
        make_public: bool = False
    ) -> dict:
        """
        上传图片到OSS
        
        Args:
            file_content: 文件内容
            filename: 原始文件名
            custom_name: 自定义文件名前缀
            subfolder: 子文件夹名称
            compress: 是否压缩图片
            make_public: 是否设置为公开访问（需要存储桶支持）
            
        Returns:
            上传结果字典
        """
        try:
            # 验证图片
            is_valid, error_msg = self._validate_image(file_content)
            if not is_valid:
                return {
                    "success": False,
                    "error": error_msg,
                    "url": None,
                    "object_key": None
                }
            
            # 压缩图片（如果需要）
            if compress:
                file_content = self._compress_image(file_content)
            
            # 生成文件名和对象键
            new_filename = self._generate_filename(filename, custom_name)
            object_key = self._get_object_key(new_filename, subfolder)
            
            # 获取MIME类型
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = 'image/jpeg'
            
            # 设置上传头部
            headers = {
                'Content-Type': mime_type,
                'Cache-Control': 'max-age=31536000'  # 缓存一年
            }
            
            # 上传文件
            result = self.bucket.put_object(
                object_key,
                file_content,
                headers=headers
            )
            
            # 生成访问URL - 签名URL有效期设置为7天
            url = self.bucket.sign_url('GET', object_key, 7 * 24 * 3600)  # 7天有效期
            
            oss_logger.info(f"图片上传成功: {object_key}")
            
            return {
                "success": True,
                "error": None,
                "url": url,
                "object_key": object_key,
                "filename": new_filename,
                "size": len(file_content),
                "etag": result.etag,
                "request_id": result.request_id
            }
            
        except OssError as e:
            error_msg = f"OSS上传失败: {e.code} - {e.message}"
            oss_logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": None,
                "object_key": None
            }
        except Exception as e:
            error_msg = f"上传过程中发生错误: {str(e)}"
            oss_logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": None,
                "object_key": None
            }
    
    def upload_from_url(
        self,
        image_url: str,
        custom_name: Optional[str] = None,
        subfolder: Optional[str] = None,
        compress: bool = True,
        make_public: bool = False
    ) -> dict:
        """
        从URL下载并上传图片
        
        Args:
            image_url: 图片URL
            custom_name: 自定义文件名前缀
            subfolder: 子文件夹名称
            compress: 是否压缩图片
            make_public: 是否设置为公开访问
            
        Returns:
            上传结果字典
        """
        try:
            import requests
            
            # 下载图片
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # 从URL获取文件名
            filename = os.path.basename(image_url.split('?')[0])
            if not filename or '.' not in filename:
                filename = 'downloaded_image.jpg'
            
            # 上传图片
            return self.upload_image(
                file_content=response.content,
                filename=filename,
                custom_name=custom_name,
                subfolder=subfolder,
                compress=compress,
                make_public=make_public
            )
            
        except Exception as e:
            error_msg = f"从URL上传图片失败: {str(e)}"
            oss_logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "url": None,
                "object_key": None
            }
    
    def delete_image(self, object_key: str) -> dict:
        """
        删除OSS中的图片
        
        Args:
            object_key: 对象键
            
        Returns:
            删除结果字典
        """
        try:
            result = self.bucket.delete_object(object_key)
            oss_logger.info(f"图片删除成功: {object_key}")
            
            return {
                "success": True,
                "error": None,
                "request_id": result.request_id
            }
            
        except OssError as e:
            error_msg = f"OSS删除失败: {e.code} - {e.message}"
            oss_logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"删除过程中发生错误: {str(e)}"
            oss_logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    def get_image_info(self, object_key: str) -> dict:
        """
        获取图片信息
        
        Args:
            object_key: 对象键
            
        Returns:
            图片信息字典
        """
        try:
            # 获取对象元数据
            metadata = self.bucket.get_object_meta(object_key)
            
            return {
                "success": True,
                "error": None,
                "size": metadata.content_length,
                "last_modified": metadata.last_modified,
                "etag": metadata.etag,
                "content_type": metadata.content_type
            }
            
        except OssError as e:
            error_msg = f"获取图片信息失败: {e.code} - {e.message}"
            oss_logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"获取信息过程中发生错误: {str(e)}"
            oss_logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

    def get_signed_url(self, object_key: str, expires: int = 7 * 24 * 3600) -> str:
        """
        获取文件的签名URL
        
        Args:
            object_key: 对象键
            expires: 过期时间（秒），默认7天
            
        Returns:
            签名URL
        """
        try:
            return self.bucket.sign_url('GET', object_key, expires)
        except Exception as e:
            oss_logger.error(f"生成签名URL失败: {str(e)}")
            return ""

    def get_public_url(self, object_key: str, custom_domain: Optional[str] = None) -> str:
        """
        获取公开访问URL（仅当存储桶为公开读取时可用）
        
        Args:
            object_key: 对象键
            custom_domain: 自定义域名
            
        Returns:
            公开访问URL
        """
        if custom_domain:
            return f"https://{custom_domain}/{object_key}"
        else:
            endpoint_without_protocol = self.endpoint.replace('https://', '').replace('http://', '')
            return f"https://{self.bucket_name}.{endpoint_without_protocol}/{object_key}" 