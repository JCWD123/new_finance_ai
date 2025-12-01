from typing import Union

from fastapi import APIRouter, HTTPException, Body

from core.article import ArticleService
from logger import task_logger
from models.models import ArticleRequest

router = APIRouter()



@router.post("/generate")
async def generate_article(request: Union[str, ArticleRequest] = Body(...)):
    """生成文章接口"""
    try:
        article_type = request if isinstance(request, str) else request.article_type
        article_service = ArticleService(article_type)
        article = await article_service.get_article()
        return {"generated_content": article}
    except Exception as e:
        task_logger.error(f"生成文章失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
