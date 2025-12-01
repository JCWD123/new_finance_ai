import os
import json
import pickle
import numpy as np
from typing import List, Dict, Optional, Tuple
import faiss
from sentence_transformers import SentenceTransformer
from datetime import datetime
import hashlib

from logger import task_logger
from models.database import PostsDB


class VectorService:
    """基于FAISS的向量检索服务，替换Dify知识库功能"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", vector_dim: int = 384):
        self.model_name = model_name
        self.vector_dim = vector_dim
        self.embeddings = SentenceTransformer(model_name)
        
        # 存储路径
        self.storage_path = "vector_storage"
        self.index_path = os.path.join(self.storage_path, "faiss_index.bin")
        self.metadata_path = os.path.join(self.storage_path, "metadata.json")
        self.documents_path = os.path.join(self.storage_path, "documents.json")
        
        # 创建存储目录
        os.makedirs(self.storage_path, exist_ok=True)
        
        # 初始化索引
        self.index = faiss.IndexFlatIP(vector_dim)  # 内积相似度
        self.metadata = {}  # 存储文档元数据
        self.documents = {}  # 存储文档内容
        self.id_to_index = {}  # 文档ID到索引位置的映射
        
        # 加载已有的索引和数据
        self._load_index()
        
        task_logger.info(f"向量服务初始化完成，当前索引文档数量: {self.index.ntotal}")

    def _load_index(self):
        """加载已保存的索引和元数据"""
        try:
            if os.path.exists(self.index_path):
                self.index = faiss.read_index(self.index_path)
                task_logger.info(f"成功加载FAISS索引，文档数量: {self.index.ntotal}")
            
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                task_logger.info(f"成功加载元数据，数量: {len(self.metadata)}")
            
            if os.path.exists(self.documents_path):
                with open(self.documents_path, 'r', encoding='utf-8') as f:
                    self.documents = json.load(f)
                task_logger.info(f"成功加载文档内容，数量: {len(self.documents)}")
            
            # 重建ID到索引的映射
            self._rebuild_id_mapping()
            
        except Exception as e:
            task_logger.error(f"加载索引失败: {str(e)}")
            # 如果加载失败，重新初始化
            self.index = faiss.IndexFlatIP(self.vector_dim)
            self.metadata = {}
            self.documents = {}
            self.id_to_index = {}

    def _rebuild_id_mapping(self):
        """重建文档ID到索引位置的映射"""
        self.id_to_index = {}
        for doc_id, meta in self.metadata.items():
            if 'index_position' in meta:
                self.id_to_index[doc_id] = meta['index_position']

    def _save_index(self):
        """保存索引和元数据到文件"""
        try:
            faiss.write_index(self.index, self.index_path)
            
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            
            with open(self.documents_path, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
            
            task_logger.info("成功保存索引和元数据")
        except Exception as e:
            task_logger.error(f"保存索引失败: {str(e)}")

    def _preprocess_text(self, text: str) -> str:
        """文本预处理，对应Dify的预处理规则"""
        import re
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text)
        # 移除URL和邮箱
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
        return text.strip()

    def _split_text(self, text: str, max_tokens: int = 512, overlap: int = 50) -> List[str]:
        """文本分段，对应Dify的分段功能"""
        # 按段落分割
        paragraphs = text.split('\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 估算token数量（简单按字符数/4估算）
            if len(current_chunk + paragraph) / 4 > max_tokens:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # 保留重叠内容
                    overlap_text = current_chunk[-overlap*4:] if len(current_chunk) > overlap*4 else current_chunk
                    current_chunk = overlap_text + "\n" + paragraph
                else:
                    current_chunk = paragraph
            else:
                current_chunk += "\n" + paragraph if current_chunk else paragraph
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def add_document(self, doc_id: str, text: str, metadata: Dict = None) -> bool:
        """添加文档到向量索引"""
        try:
            # 检查文档是否已存在
            if doc_id in self.documents:
                task_logger.info(f"文档 {doc_id} 已存在，跳过添加")
                return True
            
            # 预处理文本
            processed_text = self._preprocess_text(text)
            
            # 分段处理
            chunks = self._split_text(processed_text)
            
            # 生成向量
            vectors = self.embeddings.encode(chunks)
            
            # 添加到索引
            start_index = self.index.ntotal
            self.index.add(vectors.astype('float32'))
            
            # 存储文档内容和元数据
            self.documents[doc_id] = {
                "text": text,
                "processed_text": processed_text,
                "chunks": chunks,
                "chunk_count": len(chunks)
            }
            
            # 存储元数据
            doc_metadata = metadata or {}
            doc_metadata.update({
                "doc_id": doc_id,
                "chunk_count": len(chunks),
                "start_index": start_index,
                "end_index": start_index + len(chunks) - 1,
                "created_at": datetime.now().isoformat(),
                "vector_model": self.model_name
            })
            
            self.metadata[doc_id] = doc_metadata
            
            # 更新ID映射
            for i, chunk in enumerate(chunks):
                self.id_to_index[f"{doc_id}_chunk_{i}"] = start_index + i
            
            # 保存到文件
            self._save_index()
            
            task_logger.info(f"成功添加文档 {doc_id}，分为 {len(chunks)} 个片段")
            return True
            
        except Exception as e:
            task_logger.error(f"添加文档失败: {str(e)}")
            return False

    def search_similar(self, query: str, k: int = 5, score_threshold: float = 0.5) -> List[Dict]:
        """搜索相似文档"""
        try:
            if self.index.ntotal == 0:
                return []
            
            # 生成查询向量
            query_vector = self.embeddings.encode([query]).astype('float32')
            
            # 搜索相似向量
            scores, indices = self.index.search(query_vector, min(k * 2, self.index.ntotal))
            
            # 处理结果
            results = []
            seen_docs = set()
            
            for score, idx in zip(scores[0], indices[0]):
                if score < score_threshold:
                    continue
                
                # 找到对应的文档
                doc_id = self._find_doc_by_index(idx)
                if doc_id and doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    
                    doc_data = self.documents.get(doc_id, {})
                    doc_metadata = self.metadata.get(doc_id, {})
                    
                    result = {
                        "doc_id": doc_id,
                        "score": float(score),
                        "content": doc_data.get("text", ""),
                        "metadata": doc_metadata,
                        "chunk_hit": self._get_chunk_content(doc_id, idx)
                    }
                    results.append(result)
                    
                    if len(results) >= k:
                        break
            
            return results
            
        except Exception as e:
            task_logger.error(f"搜索失败: {str(e)}")
            return []

    def _find_doc_by_index(self, index: int) -> Optional[str]:
        """根据索引位置找到对应的文档ID"""
        for doc_id, metadata in self.metadata.items():
            start_idx = metadata.get("start_index", -1)
            end_idx = metadata.get("end_index", -1)
            if start_idx <= index <= end_idx:
                return doc_id
        return None

    def _get_chunk_content(self, doc_id: str, index: int) -> str:
        """获取特定索引位置的文档片段内容"""
        doc_data = self.documents.get(doc_id, {})
        chunks = doc_data.get("chunks", [])
        metadata = self.metadata.get(doc_id, {})
        start_idx = metadata.get("start_index", 0)
        
        chunk_idx = index - start_idx
        if 0 <= chunk_idx < len(chunks):
            return chunks[chunk_idx]
        return ""

    def get_document(self, doc_id: str) -> Optional[Dict]:
        """获取文档详情"""
        if doc_id not in self.documents:
            return None
        
        return {
            "doc_id": doc_id,
            "content": self.documents[doc_id]["text"],
            "metadata": self.metadata.get(doc_id, {}),
            "chunks": self.documents[doc_id]["chunks"]
        }

    def delete_document(self, doc_id: str) -> bool:
        """删除文档（标记删除，不实际从索引中移除）"""
        try:
            if doc_id in self.documents:
                # 标记为删除
                if doc_id in self.metadata:
                    self.metadata[doc_id]["deleted"] = True
                    self.metadata[doc_id]["deleted_at"] = datetime.now().isoformat()
                
                task_logger.info(f"成功标记删除文档 {doc_id}")
                self._save_index()
                return True
            return False
        except Exception as e:
            task_logger.error(f"删除文档失败: {str(e)}")
            return False

    def list_documents(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """列出文档"""
        active_docs = [
            {
                "doc_id": doc_id,
                "metadata": metadata
            }
            for doc_id, metadata in self.metadata.items()
            if not metadata.get("deleted", False)
        ]
        
        # 按创建时间排序
        active_docs.sort(key=lambda x: x["metadata"].get("created_at", ""), reverse=True)
        
        return active_docs[offset:offset + limit]

    def get_stats(self) -> Dict:
        """获取统计信息"""
        active_docs = sum(1 for metadata in self.metadata.values() if not metadata.get("deleted", False))
        total_chunks = sum(doc.get("chunk_count", 0) for doc in self.documents.values())
        
        return {
            "total_documents": len(self.documents),
            "active_documents": active_docs,
            "total_chunks": total_chunks,
            "index_size": self.index.ntotal,
            "vector_dimension": self.vector_dim,
            "model_name": self.model_name
        }

    def rebuild_index(self):
        """重建索引（清理删除的文档）"""
        try:
            # 获取所有未删除的文档
            active_docs = [
                (doc_id, self.documents[doc_id], self.metadata[doc_id])
                for doc_id in self.documents.keys()
                if not self.metadata.get(doc_id, {}).get("deleted", False)
            ]
            
            # 重新初始化索引
            self.index = faiss.IndexFlatIP(self.vector_dim)
            new_metadata = {}
            new_documents = {}
            self.id_to_index = {}
            
            # 重新添加所有文档
            for doc_id, doc_data, metadata in active_docs:
                chunks = doc_data["chunks"]
                vectors = self.embeddings.encode(chunks)
                
                start_index = self.index.ntotal
                self.index.add(vectors.astype('float32'))
                
                # 更新元数据
                metadata["start_index"] = start_index
                metadata["end_index"] = start_index + len(chunks) - 1
                metadata.pop("deleted", None)
                metadata.pop("deleted_at", None)
                
                new_metadata[doc_id] = metadata
                new_documents[doc_id] = doc_data
                
                # 更新ID映射
                for i in range(len(chunks)):
                    self.id_to_index[f"{doc_id}_chunk_{i}"] = start_index + i
            
            self.metadata = new_metadata
            self.documents = new_documents
            
            # 保存重建后的索引
            self._save_index()
            
            task_logger.info(f"索引重建完成，活跃文档数量: {len(active_docs)}")
            return True
            
        except Exception as e:
            task_logger.error(f"重建索引失败: {str(e)}")
            return False

    def index_exists(self) -> bool:
        """检查索引文件是否存在"""
        return (os.path.exists(self.index_path) and 
                os.path.exists(self.metadata_path) and 
                os.path.exists(self.documents_path))
    
    def clear_all(self) -> bool:
        """清除所有数据"""
        try:
            # 重新初始化内存中的数据结构
            self.index = faiss.IndexFlatL2(self.vector_dim)
            self.metadata = {}
            self.documents = {}
            self.id_to_index = {}
            self.next_idx = 0
            
            # 删除磁盘文件
            if os.path.exists(self.index_path):
                os.remove(self.index_path)
            if os.path.exists(self.metadata_path):
                os.remove(self.metadata_path)
            if os.path.exists(self.documents_path):
                os.remove(self.documents_path)
            
            task_logger.info("向量数据库已清空")
            return True
            
        except Exception as e:
            task_logger.error(f"清空数据库失败: {str(e)}")
            return False

    def save_index(self) -> bool:
        """保存索引到磁盘（公共方法）"""
        try:
            self._save_index()
            return True
        except Exception as e:
            task_logger.error(f"保存索引失败: {str(e)}")
            return False


class DocumentManager:
    """文档管理器，提供与Dify API兼容的接口"""
    
    def __init__(self):
        self.vector_service = VectorService()
        self.posts_db = PostsDB()

    async def sync_posts_to_vector(self, type_filter: List[str] = None):
        """同步帖子到向量数据库"""
        from config.settings import TYPE_MAP
        
        try:
            types_to_sync = type_filter or list(TYPE_MAP.keys())
            
            for post_type in types_to_sync:
                posts = await self.posts_db.get_posts(type=post_type, limit=None)
                
                for post in posts:
                    doc_id = post["md5"]
                    
                    # 检查是否已存在
                    if self.vector_service.get_document(doc_id):
                        continue
                    
                    # 准备元数据
                    metadata = {
                        "type": TYPE_MAP.get(post_type, post_type),
                        "date": post.get("date"),
                        "timestamp": post.get("date"),
                        "post_type": post_type,
                        "title": post.get("title", ""),
                        "source": "posts_db"
                    }
                    
                    # 添加到向量数据库
                    success = self.vector_service.add_document(
                        doc_id=doc_id,
                        text=post["mes"],
                        metadata=metadata
                    )
                    
                    if success:
                        task_logger.info(f"成功同步文档: {doc_id}")
                    else:
                        task_logger.error(f"同步文档失败: {doc_id}")
            
            task_logger.info("文档同步完成")
            return True
            
        except Exception as e:
            task_logger.error(f"同步文档失败: {str(e)}")
            return False

    def search_related_posts(self, query: str, post_type: str = None, k: int = 5) -> List[Dict]:
        """搜索相关帖子"""
        try:
            results = self.vector_service.search_similar(query, k=k * 2)
            
            # 如果指定了类型，过滤结果
            if post_type:
                results = [
                    result for result in results
                    if result.get("metadata", {}).get("post_type") == post_type
                ]
            
            return results[:k]
            
        except Exception as e:
            task_logger.error(f"搜索相关帖子失败: {str(e)}")
            return []

    def get_document_by_id(self, doc_id: str) -> Optional[Dict]:
        """根据ID获取文档"""
        return self.vector_service.get_document(doc_id)

    def add_new_post(self, post_data: Dict) -> bool:
        """添加新帖子"""
        try:
            doc_id = post_data.get("md5") or post_data.get("id")
            if not doc_id:
                task_logger.error("缺少文档ID")
                return False
            
            metadata = {
                "type": post_data.get("type", ""),
                "date": post_data.get("date"),
                "timestamp": post_data.get("date"),
                "post_type": post_data.get("post_type", ""),
                "title": post_data.get("title", ""),
                "source": "new_post"
            }
            
            return self.vector_service.add_document(
                doc_id=doc_id,
                text=post_data.get("mes", ""),
                metadata=metadata
            )
            
        except Exception as e:
            task_logger.error(f"添加新帖子失败: {str(e)}")
            return False

    def document_exists(self, doc_id: str) -> bool:
        """检查文档是否存在"""
        return self.vector_service.get_document(doc_id) is not None
    
    def add_document(self, doc_id: str, content: str, metadata: Dict = None, save_immediately: bool = True) -> bool:
        """添加文档到向量数据库"""
        success = self.vector_service.add_document(doc_id, content, metadata)
        if success and not save_immediately:
            # 如果指定不立即保存，则跳过自动保存（用于批量操作）
            pass
        return success
    
    def remove_document(self, doc_id: str) -> bool:
        """删除文档"""
        return self.vector_service.delete_document(doc_id) 