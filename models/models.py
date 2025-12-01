from pydantic import BaseModel


class ArticleRequest(BaseModel):
    article_type: str


class DifyDocumentRequest(BaseModel):
    dataset_id: str
    type: str
    document_id: str
    content: str
    metadata: dict = {}
