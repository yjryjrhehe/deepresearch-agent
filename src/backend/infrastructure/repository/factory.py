from functools import lru_cache

from .opensearch_store import AsyncOpenSearchRAGStore
from ...domain.interfaces import Retriever
from .retriever import RetrievalService
from ..llm.factory import get_rewrite_llm, get_rerank_client

@lru_cache()
def get_opensearch_store() -> AsyncOpenSearchRAGStore:
    """
    [工厂方法] 获取 AsyncOpenSearchRAGStore 单例。
    """
    return AsyncOpenSearchRAGStore()

@lru_cache()
def get_retrieval_service() -> Retriever:
    """
    工厂函数：组装并返回 RetrievalServiceImpl 实例。
    这里负责将 infrastructure 层的具体实现注入到 service 层。
    """
    return RetrievalService(
        search_repo=get_opensearch_store(),
        rewrite_llm=get_rewrite_llm(),
        rerank_client=get_rerank_client()
    )