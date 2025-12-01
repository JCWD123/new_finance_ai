from pymongo import MongoClient
from pymongo.errors import (
    ConnectionFailure,
    PyMongoError,
    DuplicateKeyError,
    BulkWriteError,
)

from config.settings import MONGODB_SETTINGS
from logger import task_logger


class MongoDBService:
    _instance = None
    _is_initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._is_initialized:
            try:
                self.client = MongoClient(MONGODB_SETTINGS["uri"])
                self.client.admin.command("ping")
                self.db = self.client[MONGODB_SETTINGS["database"]]
                task_logger.info("✅ MongoDB连接成功")
                MongoDBService._is_initialized = True
            except ConnectionFailure as e:
                task_logger.error(f"❌ MongoDB连接失败: {e}", exc_info=True)

    def close(self):
        """安全关闭MongoDB连接"""
        if hasattr(self, "client") and self.client:
            try:
                self.client.close()
                self.client = None
                MongoDBService._is_initialized = False  # 重置初始化状态
            except Exception:
                pass  # 忽略关闭时的错误

    def __del__(self):
        """
        析构函数，使用异常捕获防止在Python关闭时出错
        """
        try:
            self.close()
        except (ImportError, AttributeError, TypeError):
            # 捕获Python关闭过程中可能发生的ImportError
            # 以及其他可能的错误类型
            pass

    def fetch_data(
        self,
        collection_name: str,
        query: dict = None,
        projection: dict = None,
        sort_field: str = None,
        sort_order: int = -1,
        skip: int = None,
        limit: int = None,
    ):
        """
        查询指定集合中的数据
        :param collection_name: 集合名称
        :param projection: 返回字段投影
        :param sort_field: 排序字段
        :param sort_order: 排序方式（-1降序/1升序）
        :param limit: 返回结果数量限制
        :return: 文档列表
        """
        try:
            collection = self.db[collection_name]

            # 构建查询条件
            query = query or {}

            # 使用投影优化查询性能
            projection = projection or {"_id": 0}

            # 执行查询并添加排序
            cursor = collection.find(filter=query, projection=projection)

            if sort_field:
                cursor = cursor.sort(sort_field, sort_order)

            if skip:
                cursor = cursor.skip(skip)

            if limit:
                cursor = cursor.limit(limit)

            return list(cursor)
        except PyMongoError as e:
            task_logger.error(f"❌ 数据库查询错误: {e}")
            return []

    def batch_fetch_by_ids(
        self,
        collection_name: str,
        id_list: list[str],
        ids_field: str = "id",
        projection: dict = None,
    ):
        """
        批量查询指定集合中的数据
        :param collection_name: 集合名称
        :param id_list: 需要查询的ID列表
        :param ids_field: ID字段名称
        :param projection: 返回字段投影
        :return: 文档列表
        """
        try:
            query = {ids_field: {"$in": id_list}}
            projection = projection or {"_id": 0}
            result = self.fetch_data(collection_name, query, projection)

            return result
        except PyMongoError as e:
            task_logger.error(f"❌ 批量查询错误: {e}")
            return []

    def check_id_exists(
        self, collection_name: str, id: str, id_field: str = "id"
    ) -> bool:
        """
        检查指定ID是否已存在集合中
        :param collection_name: 集合名称
        :param id: 要检查的唯一标识符
        :param id_field: ID字段名称
        :return: 存在返回True，否则返回False
        """
        try:
            collection = self.db[collection_name]
            result = collection.find_one(
                {id_field: id}, projection={"_id": 1}  # 只查询_id字段优化性能
            )
            return result is not None
        except PyMongoError as e:
            task_logger.error(f"❌ ID查询失败: {e}")
            return False

    def insert_document(
        self, collection_name: str, document: dict, check_keys: bool = True
    ) -> str:
        """
        插入单个文档
        :param collection_name: 集合名称
        :param document: 文档内容
        :param check_keys: 是否检查 '_id' 冲突
        :return: 插入的文档ID (失败返回空字符串)
        """
        try:
            result = self.db[collection_name].insert_one(document)
            task_logger.info(
                f"{collection_name} ✅ 文档插入成功 | ID: {result.inserted_id}"
            )
            return str(result.inserted_id)
        except DuplicateKeyError as e:
            if check_keys:
                task_logger.info(
                    f"{collection_name} ⚠️ 文档 _id 冲突: {e.details.get('errmsg')}"
                )
            else:
                task_logger.info(
                    f"{collection_name} ❌ 键值冲突: {e.details.get('errmsg')}"
                )
            return False
        except PyMongoError as e:
            task_logger.info(f"{collection_name} ❌ 文档插入失败: {e}")
            return False

    def insert_many(
        self,
        collection_name: str,
        documents: list[dict],
        ordered: bool = True,
        bypass_validation: bool = False,
    ) -> list[str]:
        """
        批量插入文档
        :param collection_name: 集合名称
        :param ordered: 是否顺序写入（False时允许部分成功）
        :param bypass_validation: 是否跳过数据验证
        :return: 成功插入的文档ID列表
        """
        try:
            result = self.db[collection_name].insert_many(
                documents, ordered=ordered, bypass_document_validation=bypass_validation
            )
            success_count = len(result.inserted_ids)
            task_logger.info(
                f"✅ 批量插入完成 | 成功: {success_count}/{len(documents)}"
            )
            return [str(id) for id in result.inserted_ids]
        except BulkWriteError as e:
            success_ids = [str(id) for id in e.details["insertedIds"].values()]
            task_logger.info(
                f"⚠️ 批量插入部分成功 | 成功: {len(success_ids)} 失败: {e.details['nInserted']}"
            )
            return success_ids
        except PyMongoError as e:
            task_logger.info(f"❌ 批量插入失败: {e}")
            return []

    def update_document(
        self,
        collection_name: str,
        query: dict,
        update: dict,
        upsert: bool = False,
    ) -> bool:
        """
        更新单个文档
        :param collection_name: 集合名称
        :param query: 查询条件
        :param update: 更新内容
        :param upsert: 是否插入新文档
        :return: 更新结果（True/False）
        """
        try:
            result = self.db[collection_name].update_one(
                filter=query, update=update, upsert=upsert
            )
            if result.modified_count > 0:
                task_logger.info(f"✅ 文档更新成功 | ID: {query.get('id')}")
                return True
            else:
                task_logger.info(f"❌ 文档未修改或不存在 | ID: {query.get('id')}")
                return False
        except PyMongoError as e:
            task_logger.info(f"❌ 文档更新失败: {e}")
            return False
