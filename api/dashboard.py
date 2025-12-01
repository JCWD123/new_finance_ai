import pandas as pd
from fastapi import APIRouter, HTTPException

from core.news import NewsService
from logger import task_logger

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_data():
    """获取资讯数据"""
    try:
        news_service = NewsService()
        morning_points = await news_service.get_dashboard_news("ReadMorning")
        logical_points = await news_service.get_dashboard_news("LogicalReview")
        points = morning_points + logical_points if logical_points else morning_points
        points = [
            {
                "event_summary": i["event_summary"],
                "date": i["date"],
                "id": i["event_id"],
            }
            for i in points
        ]
        return {"points": points}
    except Exception as e:
        task_logger.error(f"获取资讯数据失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/{news_id}")
async def get_news_detail(news_id: str):
    """获取新闻详情"""
    try:
        news_service = NewsService()
        morning_points = await news_service.get_dashboard_news("ReadMorning")
        logical_points = await news_service.get_dashboard_news("LogicalReview")
        events = morning_points + logical_points if logical_points else morning_points
        events_df = pd.DataFrame(events)
        event = events_df[events_df["event_id"] == news_id].to_dict(orient="records")[0]
        links = {"internal": [], "abroad": []}
        for link in event["links"]:
            if link["from"] == "internal":
                links["internal"].append(link)
            else:
                links["abroad"].append(link)
        return {
            "news_id": event["event_id"],
            "title": event["title"],
            "content": event["content"].strip(),
            "links": links,
            "score": event["score"],
        }
    except Exception as e:
        task_logger.error(f"获取新闻详情失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exponentialFolding/")
async def get_exponential_folding():
    """获取指数折线系数"""
    try:
        news_service = NewsService()
        data = await news_service.get_market_data()
        return data
    except Exception as e:
        task_logger.error(f"获取指数数据失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
