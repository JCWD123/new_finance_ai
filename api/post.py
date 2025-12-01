from datetime import datetime
import asyncio

from fastapi import APIRouter, Body, Request

from config.settings import TYPE_MAP, DIFY_CONFIG
from core.posts import PostsService
from logger import api_logger
from models.database import PostsDB
from models.models import DifyDocumentRequest
from services.vector_service import DocumentManager
from utils.tools import extract_square_bracket_contents

router = APIRouter()

posts_db = PostsDB()
posts_service = PostsService()
doc_manager = DocumentManager()


@router.get("/summarize")
async def get_summarize():
    """获取文章观点归纳提炼"""
    api_logger.info("获取文章观点归纳提炼")
    posts_analysis = await posts_db.get_posts_analysis(
        "ReadMorning", limit=7
    ) + await posts_db.get_posts_analysis("LogicalReview", limit=7)
    posts_ids = [i["id"] for i in posts_analysis]
    posts = await posts_db.get_posts_by_ids(posts_ids)
    posts = [
        {**pa, **post}
        for pa in posts_analysis
        for post in posts
        if post["md5"] == pa["id"]
    ]
    result = {"ReadMorning": [], "LogicalReview": []}
    for post in posts:
        post["date"] = datetime.fromtimestamp(post["date"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        post_result = {
            "id": post["id"],
            "content": post["mes"],
            "content_analysis": post["content_analysis"],
            "date": post["date"],
        }
        if post["type"] == "ReadMorning":
            result["ReadMorning"].append(post_result)
        else:
            result["LogicalReview"].append(post_result)

    result["ReadMorning"] = sorted(
        result["ReadMorning"], key=lambda x: x["date"], reverse=True
    )
    result["LogicalReview"] = sorted(
        result["LogicalReview"], key=lambda x: x["date"], reverse=True
    )
    api_logger.info(f"获取文章观点归纳提炼完成")
    return result


@router.get("/serums/{page}")
async def get_serums(page: int = 1):
    """获取精华提炼"""
    api_logger.info("获取精华提炼")
    posts_analysis = await posts_db.get_posts_analysis(
        "Essence", limit=10, skip=(page - 1) * 10
    )
    posts_ids = [i["id"] for i in posts_analysis]
    posts = await posts_db.get_posts_by_ids(posts_ids)
    posts = [
        {**pa, **post}
        for pa in posts_analysis
        for post in posts
        if post["md5"] == pa["id"]
    ]
    posts = [
        {
            "id": post["id"],
            "title": post.get("title", extract_square_bracket_contents([post])[0]),
            "content": post["mes"],
            "content_analysis": post["content_analysis"],
            "date": post["date"],
        }
        for post in posts
    ]
    api_logger.info(f"获取精华提炼完成")

    return posts


@router.get("/market")
async def get_market():
    """获取金融行情市场分析"""
    api_logger.info("获取金融行情市场分析")
    posts = await get_summarize()
    market = await posts_service.financial_market_analysis(posts)
    api_logger.info(f"获取金融行情市场分析完成")

    return market


@router.get("/models")
async def get_models():
    """获取金融板块分析"""
    api_logger.info("获取金融板块分析")
    posts = await get_summarize()
    models = await posts_service.financial_models_analysis(posts)
    api_logger.info(f"获取金融板块分析完成")

    return models


@router.post("/vector_document")
async def vector_document(request: DifyDocumentRequest = Body(...)):
    """向量文档处理"""
    api_logger.info("向量文档处理")
    
    type_name = TYPE_MAP.get(request.type, None)
    doc_id = request.document_id
    content = request.content
    metadata = request.metadata
    
    if not type_name:
        api_logger.error(f"Invalid type: {request.type}")
        return {"error": "Invalid document type"}
    
    # 检查文档是否已存在
    existing_doc = doc_manager.get_document_by_id(doc_id)
    if existing_doc:
        return {"message": "Document already exists", "doc_id": doc_id}

    # 准备完整的元数据
    full_metadata = {
        "type": type_name,
        "post_type": request.type,
        "source": "api_upload"
    }
    if metadata:
        full_metadata.update(metadata)
    
    # 添加文档到向量数据库
    success = doc_manager.vector_service.add_document(
        doc_id=doc_id,
        text=content,
        metadata=full_metadata
    )
    
    if success:
        api_logger.info(f"向量文档处理完成: {doc_id}")
        return {"message": "Document added successfully", "doc_id": doc_id}
    else:
        api_logger.error(f"向量文档处理失败: {doc_id}")
        return {"error": "Failed to add document"}


@router.get("/ref-post/{post_id}")
async def get_ref_post(post_id: str):
    """获取参考文章"""
    api_logger.info(f"获取参考文章")
    post = await posts_db.get_posts_by_ids([post_id])
    api_logger.info(f"获取参考文章完成")
    post = {
        "id": post[0]["md5"],
        "date": datetime.fromtimestamp(post[0]["date"]).strftime("%Y-%m-%d %H:%M:%S"),
        "content": post[0]["mes"],
        "type": post[0]["type"],
    }

    return post


@router.post("/v1/pro-documents")
async def pro_documents(request: Request):
    """
    处理向量数据库文档API的代理端点
    """
    api_logger.info("处理向量数据库文档...")
    
    # 获取最近的帖子
    recent_posts = []
    for type in TYPE_MAP.keys():
        if type == "ess":  # 修正类型名称
            continue
        recent_posts.extend(await posts_db.get_posts(type, limit=5))
    
    recv_posts = await request.json()
    existing_ids = [i.get("title", "") for i in recv_posts]
    
    # 处理最近的帖子
    for post in recent_posts:
        if post["md5"] not in existing_ids:
            try:
                # 检查文档是否在向量数据库中存在
                doc_data = doc_manager.get_document_by_id(post["md5"])
                
                if not doc_data:
                    # 如果不存在，添加到向量数据库
                    metadata = {
                        "date": post["date"], 
                        "type": post["type"],
                        "post_type": post["type"],
                        "title": post.get("title", "")
                    }
                    
                    success = doc_manager.add_new_post({
                        "md5": post["md5"],
                        "mes": post["mes"],
                        "type": TYPE_MAP.get(post["type"], post["type"]),
                        "post_type": post["type"],
                        "date": post["date"],
                        "title": post.get("title", "")
                    })
                    
                    if not success:
                        api_logger.error(f"添加文档到向量数据库失败: {post['md5']}")
                        continue
                    
                    doc_data = doc_manager.get_document_by_id(post["md5"])
                
                if doc_data:
                    # 构建兼容的数据格式
                    data = {
                        "metadata": {
                            "_source": "vector_knowledge",
                            "dataset_id": "local_vector_db",
                            "dataset_name": "AI学长向量库",
                            "document_id": post["md5"],
                            "document_name": post["md5"],
                            "document_data_source_type": "upload_file",
                            "segment_id": f"{post['md5']}_segment",
                            "retriever_from": "vector_search",
                            "score": 0.8,
                            "segment_hit_count": len(doc_data.get("chunks", [])),
                            "segment_word_count": len(post["mes"]),
                            "segment_position": 1,
                            "segment_index_node_hash": post["md5"],
                            "doc_metadata": {"date": post["date"], "type": post["type"]},
                            "position": 1,
                        },
                        "title": post["md5"],
                        "content": post["mes"],
                    }
                    recv_posts.append(data)
                    
            except Exception as e:
                api_logger.error(f"处理文档失败: {post['md5']}, 错误: {str(e)}")
                continue
    
    # 更新链接信息
    for index, post in enumerate(recv_posts):
        try:
            doc_metadata = post.get('metadata', {}).get("doc_metadata", {})
            post_type = doc_metadata.get('type', '未知')
            post_date = doc_metadata.get('date', 0)
            
            if isinstance(post_date, (int, float)):
                date_str = datetime.fromtimestamp(post_date).strftime("%Y-%m-%d %H:%M:%S")
            else:
                date_str = str(post_date)
            
            post["link_title"] = f"{post_type} - {date_str}"
            post["link_url"] = f"http://localhost:8080/api/ref-post/{post['title']}"
            recv_posts[index] = post
        except Exception as e:
            api_logger.error(f"更新链接信息失败: {str(e)}")
            continue

    api_logger.info(f"处理向量数据库文档完成，返回 {len(recv_posts)} 个文档")
    return recv_posts


@router.get("/vector/search")
async def search_vector_documents(query: str, k: int = 5, post_type: str = None):
    """搜索向量数据库中的相关文档"""
    api_logger.info(f"搜索向量文档: {query}")
    
    try:
        results = doc_manager.search_related_posts(query=query, post_type=post_type, k=k)
        
        # 格式化返回结果
        formatted_results = []
        for result in results:
            metadata = result.get("metadata", {})
            formatted_result = {
                "doc_id": result["doc_id"],
                "score": result["score"],
                "content": result["content"][:500] + "..." if len(result["content"]) > 500 else result["content"],
                "chunk_hit": result.get("chunk_hit", ""),
                "type": metadata.get("type", ""),
                "date": metadata.get("date", ""),
                "title": metadata.get("title", "")
            }
            formatted_results.append(formatted_result)
        
        api_logger.info(f"搜索完成，返回 {len(formatted_results)} 个结果")
        return {"results": formatted_results, "total": len(formatted_results)}
        
    except Exception as e:
        api_logger.error(f"搜索向量文档失败: {str(e)}")
        return {"error": str(e), "results": [], "total": 0}


@router.get("/vector/stats")
async def get_vector_stats():
    """获取向量数据库统计信息"""
    api_logger.info("获取向量数据库统计信息")
    
    try:
        stats = doc_manager.vector_service.get_stats()
        api_logger.info("获取统计信息完成")
        return stats
    except Exception as e:
        api_logger.error(f"获取统计信息失败: {str(e)}")
        return {"error": str(e)}


@router.get("/vector/documents")
async def list_vector_documents(limit: int = 20, offset: int = 0):
    """列出向量数据库中的文档"""
    api_logger.info(f"列出向量文档: limit={limit}, offset={offset}")
    
    try:
        documents = doc_manager.vector_service.list_documents(limit=limit, offset=offset)
        api_logger.info(f"列出文档完成，返回 {len(documents)} 个文档")
        return {"documents": documents, "total": len(documents)}
    except Exception as e:
        api_logger.error(f"列出文档失败: {str(e)}")
        return {"error": str(e), "documents": [], "total": 0}


@router.delete("/vector/document/{doc_id}")
async def delete_vector_document(doc_id: str):
    """删除向量数据库中的文档"""
    api_logger.info(f"删除向量文档: {doc_id}")
    
    try:
        success = doc_manager.vector_service.delete_document(doc_id)
        if success:
            api_logger.info(f"删除文档完成: {doc_id}")
            return {"message": "Document deleted successfully", "doc_id": doc_id}
        else:
            api_logger.error(f"删除文档失败: {doc_id}")
            return {"error": "Document not found or deletion failed", "doc_id": doc_id}
    except Exception as e:
        api_logger.error(f"删除文档失败: {str(e)}")
        return {"error": str(e)}


@router.post("/vector/rebuild")
async def rebuild_vector_index():
    """重建向量索引"""
    api_logger.info("开始重建向量索引")
    
    try:
        success = doc_manager.vector_service.rebuild_index()
        if success:
            api_logger.info("重建向量索引完成")
            return {"message": "Index rebuilt successfully"}
        else:
            api_logger.error("重建向量索引失败")
            return {"error": "Failed to rebuild index"}
    except Exception as e:
        api_logger.error(f"重建向量索引失败: {str(e)}")
        return {"error": str(e)}
