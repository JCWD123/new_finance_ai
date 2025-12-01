import json

import requests

from models.database import PostsDB


class DifyDatasetAPI:
    def __init__(self, api_key, base_url="http://localhost"):
        """
        初始化DatasetAPI类

        参数:
            api_key (str): API密钥
            base_url (str): API基础URL，默认为http://localhost
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_document_by_text(
        self,
        dataset_id,
        name,
        text,
        indexing_technique="high_quality",
        doc_form="text_model",  # 默认使用普通文本模式
        doc_language=None,
        process_mode="automatic",  # 默认使用自动模式
        pre_processing_rules=None,
        segmentation=None,
        subchunk_segmentation=None,
        parent_mode=None,  # 父分段召回模式
        retrieval_model=None,
        embedding_model=None,
        embedding_model_provider=None,
    ):
        """
        通过文本创建文档，支持多种模式

        参数:
            dataset_id (str): 数据集ID
            name (str): 文档名称
            text (str): 文档文本内容
            indexing_technique (str): 索引技术，默认为"high_quality"
            doc_form (str): 索引内容形式，可选值：
                - text_model: 普通文本模式（默认）
                - hierarchical_model: 父子分段模式
                - qa_model: 问答模式
            doc_language (str): 文档语言，在Q&A模式下指定
            process_mode (str): 处理模式，"automatic"（自动）或"custom"（自定义）,以及"hierarchical"（父子分段）
            pre_processing_rules (list): 预处理规则列表
            segmentation (dict): 分段规则
            subchunk_segmentation (dict): 子分段规则
            parent_mode (str): 父分段召回模式，可选值：
                - full-doc: 全文召回
                - paragraph: 段落召回
            retrieval_model (dict): 检索模式配置
            embedding_model (str): Embedding模型名称
            embedding_model_provider (str): Embedding模型供应商

        返回:
            dict: API响应
        """
        url = f"{self.base_url}/v1/datasets/{dataset_id}/document/create-by-text"

        # 构建处理规则
        process_rule = {"mode": process_mode}

        # 如果是自定义模式，添加规则
        if process_mode == "custom" or process_mode == "hierarchical":
            rules = {}

            # 添加预处理规则
            if pre_processing_rules is not None:
                rules["pre_processing_rules"] = pre_processing_rules

            # 如果是父子分段模式，添加分段规则
            if doc_form == "hierarchical_model":
                if parent_mode:
                    rules["parent_mode"] = parent_mode
            # 分段规则
            if segmentation is not None:
                rules["segmentation"] = segmentation
            else:
                # 默认分段规则
                segment_rule = {"separator": "\\n\\n", "max_tokens": 1024}
                rules["segmentation"] = segment_rule

            # 子分段规则
            if subchunk_segmentation is not None:
                rules["subchunk_segmentation"] = subchunk_segmentation
            else:
                # 默认子分段规则
                rules["subchunk_segmentation"] = {"separator": "\\n", "max_tokens": 512}

            # 设置规则
            if rules:
                process_rule["rules"] = rules

        # 构建有效载荷
        payload = {
            "name": name,
            "text": text,
            "indexing_technique": indexing_technique,
            "doc_form": doc_form,
            "process_rule": process_rule,
        }

        # 添加可选参数
        if doc_language:
            payload["doc_language"] = doc_language

        if retrieval_model:
            payload["retrieval_model"] = retrieval_model

        if embedding_model:
            payload["embedding_model"] = embedding_model

        if embedding_model_provider:
            payload["embedding_model_provider"] = embedding_model_provider

        # 打印请求体便于调试
        # print("请求体: ", json.dumps(payload, ensure_ascii=False, indent=2))

        response = requests.post(
            url, headers=self.headers, data=json.dumps(payload, ensure_ascii=False)
        )
        return response.json()

    def update_document_metadata(self, dataset_id, operation_data):
        """
        更新文档元数据

        参数:
            dataset_id (str): 数据集ID
            operation_data (list): 操作数据列表，包含文档ID和元数据列表

        返回:
            dict: API响应
        """
        url = f"{self.base_url}/v1/datasets/{dataset_id}/documents/metadata"

        payload = {"operation_data": operation_data}

        response = requests.post(
            url, headers=self.headers, data=json.dumps(payload, ensure_ascii=False)
        )
        return response.json()

    def get_documents(self, dataset_id, page=1, limit=20, search=None):
        """
        获取数据集中的文档列表

        参数:
            dataset_id (str): 数据集ID
            page (int): 页码，默认为1
            limit (int): 每页数量，默认为20
            search (str): 搜索关键词

        返回:
            dict: API响应，包含文档列表信息
        """
        url = f"{self.base_url}/v1/datasets/{dataset_id}/documents"

        # 构建查询参数
        params = {"page": page, "limit": limit}
        # 添加可选的搜索参数
        if search:
            params["keyword"] = search

        # 对于GET请求，使用不包含Content-Type的头
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response = requests.get(url, headers=headers, params=params)
        return response.json()

    def get_dataset_metadata(self, dataset_id):
        """
        获取数据集元数据

        参数:
            dataset_id (str): 数据集ID

        返回:
            dict: API响应，包含数据集的元数据信息
        """
        url = f"{self.base_url}/v1/datasets/{dataset_id}/metadata"

        # 对于GET请求，不需要Content-Type头
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response = requests.get(url, headers=headers)
        return response.json()

    def get_segment(self, dataset_id, document_id):
        url = (
            f"{self.base_url}/v1/datasets/{dataset_id}/documents/{document_id}/segments"
        )
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(url, headers=headers)
        return response.json()

    def delete_document(self, dataset_id, document_id):
        """
        删除知识库文档

        参数:
            dataset_id (str): 数据集ID
            document_id (str): 文档ID

        返回:
            bool: 删除是否成功，成功返回True，失败返回False
        """
        url = f"{self.base_url}/v1/datasets/{dataset_id}/documents/{document_id}"

        # 对于DELETE请求，只需要Authorization头
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response = requests.delete(url, headers=headers)

        # 根据API文档，成功删除返回204 No Content
        return response.json() == 204


if __name__ == "__main__":
    import asyncio
    from tqdm import tqdm

    TYPE_MAP = {
        "ReadMorning": "早间必读",
        "LogicalReview": "逻辑复盘",
        "Essence": "精华",
    }
    posts_db = PostsDB()

    # 创建API实例
    api = DifyDatasetAPI(
        api_key="dataset-6CpbD4ZcgcyzBRDuAFZVyMlJ", base_url="http://121.43.136.106/"
    )
    dataset_id = "abb12faf-b9b1-4b2f-9671-6a0202f727de"

    # 获取元数据
    metadata = api.get_dataset_metadata(dataset_id=dataset_id)

    # 获取帖子并处理
    for type, name in TYPE_MAP.items():
        posts = asyncio.run(posts_db.get_posts(type=type, limit=None))
        for post in tqdm(posts, desc=f"处理{name}帖子"):
            post["type"] = name
            documents = api.get_documents(dataset_id=dataset_id, search=post["md5"])
            if documents.get("data", []):
                continue
            # 创建文档
            document_result = api.create_document_by_text(
                dataset_id=dataset_id,
                name=post["md5"],
                text=post["mes"],
                doc_form="hierarchical_model",  # 使用父子分段模式
                process_mode="hierarchical",
                parent_mode="full-doc",
                subchunk_segmentation={
                    "separator": "\\n",  # 段落分隔符
                    "max_tokens": 512,  # 最大512字符
                    "chunk_overlap": 50,  # 分段重叠50个字符
                },
                pre_processing_rules=[
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": True},
                ],
            )

            # 准备元数据
            metadata_list = [
                {"id": item["id"], "value": post[item["name"]], "name": item["name"]}
                for item in metadata["doc_metadata"]
            ]

            # 更新文档元数据
            operation_data = [
                {
                    "document_id": document_result["document"]["id"],
                    "metadata_list": metadata_list,
                }
            ]
            metadata_result = api.update_document_metadata(
                dataset_id=dataset_id, operation_data=operation_data
            )
            print(post["md5"])

    # 删除不在库里面的知识库文档
    for page in range(1, 100):
        documents = api.get_documents(dataset_id=dataset_id, page=page, limit=100)
        if documents.get("data", []):
            for document in documents.get("data", []):
                if asyncio.run(posts_db.get_posts_by_ids([document["name"]])):
                    continue
                else:
                    delete_status = api.delete_document(
                        dataset_id=dataset_id, document_id=document["id"]
                    )
                    print(document["name"], delete_status)
        else:
            break
