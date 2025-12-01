from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from logger import task_logger

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def read_root():
    with open("static/index.html") as f:
        return f.read()


@router.get("/generate", response_class=HTMLResponse)
async def generate_page(type: str = None, from_: str = None):
    """Generate page with optional article type parameter"""
    try:
        with open("static/generate.html") as f:
            html = f.read()
            if type:
                # Insert the article type into the page
                html = html.replace(
                    'id="articleType"', f'id="articleType" data-initial-type="{type}"'
                )
            return html
    except Exception as e:
        task_logger.error(f"加载生成页面失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="页面加载失败")
