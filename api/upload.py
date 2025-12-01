from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Optional
import asyncio

from services.oss_uploader import OSSImageUploader
from config.settings import OSS_CONFIG
from logger import api_logger

router = APIRouter()

# 初始化OSS上传器
try:
    oss_uploader = OSSImageUploader(
        access_key_id=OSS_CONFIG["access_key_id"],
        access_key_secret=OSS_CONFIG["access_key_secret"],
        endpoint=OSS_CONFIG["endpoint"],
        bucket_name=OSS_CONFIG["bucket_name"],
        base_path=OSS_CONFIG["base_path"]
    )
except Exception as e:
    api_logger.error(f"OSS上传器初始化失败: {str(e)}")
    oss_uploader = None

@router.post("/upload/image")
async def upload_image(
    file: UploadFile = File(...),
    custom_name: Optional[str] = Form(None),
    subfolder: Optional[str] = Form(None),
    compress: bool = Form(True)
):
    """
    上传图片文件到OSS
    
    Args:
        file: 上传的图片文件
        custom_name: 自定义文件名前缀
        subfolder: 子文件夹名称
        compress: 是否压缩图片
    """
    if not oss_uploader:
        raise HTTPException(status_code=500, detail="OSS服务未配置")
    
    try:
        # 检查文件类型
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="只支持图片文件")
        
        # 读取文件内容
        file_content = await file.read()
        
        # 在线程池中执行上传操作
        def do_upload():
            return oss_uploader.upload_image(
                file_content=file_content,
                filename=file.filename,
                custom_name=custom_name,
                subfolder=subfolder,
                compress=compress
            )
        
        result = await asyncio.to_thread(do_upload)
        
        if result["success"]:
            api_logger.info(f"图片上传成功: {result['object_key']}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "图片上传成功",
                    "data": {
                        "url": result["url"],
                        "object_key": result["object_key"],
                        "filename": result["filename"],
                        "size": result["size"]
                    }
                }
            )
        else:
            api_logger.error(f"图片上传失败: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"上传接口异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

@router.post("/upload/image-from-url")
async def upload_image_from_url(
    image_url: str = Form(...),
    custom_name: Optional[str] = Form(None),
    subfolder: Optional[str] = Form(None),
    compress: bool = Form(True)
):
    """
    从URL下载并上传图片到OSS
    
    Args:
        image_url: 图片URL
        custom_name: 自定义文件名前缀
        subfolder: 子文件夹名称
        compress: 是否压缩图片
    """
    if not oss_uploader:
        raise HTTPException(status_code=500, detail="OSS服务未配置")
    
    try:
        # 在线程池中执行上传操作
        def do_upload():
            return oss_uploader.upload_from_url(
                image_url=image_url,
                custom_name=custom_name,
                subfolder=subfolder,
                compress=compress
            )
        
        result = await asyncio.to_thread(do_upload)
        
        if result["success"]:
            api_logger.info(f"从URL上传图片成功: {result['object_key']}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "图片上传成功",
                    "data": {
                        "url": result["url"],
                        "object_key": result["object_key"],
                        "filename": result["filename"],
                        "size": result["size"]
                    }
                }
            )
        else:
            api_logger.error(f"从URL上传图片失败: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"URL上传接口异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

@router.delete("/upload/image/{object_key:path}")
async def delete_image(object_key: str):
    """
    删除OSS中的图片
    
    Args:
        object_key: 对象键
    """
    if not oss_uploader:
        raise HTTPException(status_code=500, detail="OSS服务未配置")
    
    try:
        # 在线程池中执行删除操作
        def do_delete():
            return oss_uploader.delete_image(object_key)
        
        result = await asyncio.to_thread(do_delete)
        
        if result["success"]:
            api_logger.info(f"图片删除成功: {object_key}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "图片删除成功"
                }
            )
        else:
            api_logger.error(f"图片删除失败: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"删除接口异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@router.get("/upload/image-info/{object_key:path}")
async def get_image_info(object_key: str):
    """
    获取图片信息
    
    Args:
        object_key: 对象键
    """
    if not oss_uploader:
        raise HTTPException(status_code=500, detail="OSS服务未配置")
    
    try:
        # 在线程池中执行获取信息操作
        def do_get_info():
            return oss_uploader.get_image_info(object_key)
        
        result = await asyncio.to_thread(do_get_info)
        
        if result["success"]:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "获取图片信息成功",
                    "data": {
                        "size": result["size"],
                        "last_modified": result["last_modified"],
                        "etag": result["etag"],
                        "content_type": result["content_type"]
                    }
                }
            )
        else:
            api_logger.error(f"获取图片信息失败: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        api_logger.error(f"获取信息接口异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取信息失败: {str(e)}") 