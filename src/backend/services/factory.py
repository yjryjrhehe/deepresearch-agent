import logging
from functools import lru_cache

from ..domain.interfaces import Retriever
# 1. 导入 Service 类
from .ingestion_service import IngestionService
from .retrieval_service import RetrievalService

# 2. 导入其他基础设施的工厂函数
from ..infrastructure.parse.factory import (
    get_docling_parser,
    get_llm_preprocessor,
    get_markdown_splitter
)
from ..infrastructure.repository.factory import get_opensearch_store
from ..infrastructure.llm.factory import get_rewrite_llm, get_rerank_client

log = logging.getLogger(__name__)

@lru_cache()
def get_ingestion_service() -> IngestionService:
    """
    [工厂方法] 组装并获取 IngestionService 单例。
    
    职责：
    1. 调用底层组件的工厂方法获取实例。
    2. 将这些实例注入到 IngestionService 中。
    3. 返回组装好的 Service。
    """
    log.info("正在组装 IngestionService...")
    
    try:
        # 获取依赖实例
        parser_instance = get_docling_parser()
        splitter_instance = get_markdown_splitter()
        preprocessor_instance = get_llm_preprocessor()
        store_instance = get_opensearch_store()
        
        # 注入依赖并实例化
        service = IngestionService(
            parser=parser_instance,
            splitter=splitter_instance,
            preprocessor=preprocessor_instance,
            store=store_instance
        )
        
        return service
        
    except Exception as e:
        log.error(f"IngestionService 工厂初始化失败: {e}", exc_info=True)
        raise e
    
# ==========================================
# 工厂方法 (Dependency Injection Entry Point)
# ==========================================

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