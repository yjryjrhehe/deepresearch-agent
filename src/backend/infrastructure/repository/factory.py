from functools import lru_cache

from .opensearch_store import AsyncOpenSearchRAGStore

@lru_cache()
def get_opensearch_store() -> AsyncOpenSearchRAGStore:
    """
    [工厂方法] 获取 AsyncOpenSearchRAGStore 单例。
    """
    return AsyncOpenSearchRAGStore()