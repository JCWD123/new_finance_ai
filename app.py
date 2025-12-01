from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import article, dashboard, page, post, chat
from logger import api_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期管理器"""
    # # 启动时运行
    # init_scheduler()
    # scheduler.start()
    # app_logger.info("调度器已启动")

    yield  # FastAPI 运行中

    # # 关闭时运行
    # scheduler.shutdown()
    # app_logger.info("调度器已关闭")

    # 关闭数据库连接
    from services.mongodb import MongoDBService

    db_service = MongoDBService()
    db_service.close()
    api_logger.info("数据库连接已关闭")


app = FastAPI(lifespan=lifespan)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 路由注册
app.include_router(page.router, prefix="")
app.include_router(article.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(post.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


# 在FastAPI初始化后添加中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = int(datetime.now().timestamp())
    response = await call_next(request)
    process_time = (int(datetime.now().timestamp()) - start_time) * 1000
    api_logger.info(
        f"{request.method} {request.url} - Status: {response.status_code} - {process_time:.2f}ms"
    )
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8080, workers=4)
