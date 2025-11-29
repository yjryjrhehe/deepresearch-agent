from functools import lru_cache
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# 导入配置
from ...core.config import settings
# 导入自定义的 Reranker Client 类
from .reranker import TEIRerankerClient 

# ==========================================
#  通用构建辅助函数 (核心解耦逻辑)
# ==========================================
def _create_chat_llm(config_name: str, temperature: float = 0, max_retries: int = 3) -> ChatOpenAI:
    """
    私有辅助函数：根据配置名称动态创建 ChatOpenAI 实例。
    
    Args:
        config_name: 对应 config.py 中 get_llm_config_by_name 支持的名称 
                     (e.g., "rewrite", "research", "preprocess")
        temperature: 模型温度
        max_retries: 最大重试次数
    """
    # 1. 动态获取配置对象 (类型为 LLMProviderConfig)
    config = settings.get_llm_config_by_name(config_name)
    
    # 2. 统一实例化
    return ChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        temperature=temperature,
        max_retries=max_retries
    )

# ==========================================
# 1. 预处理 LLM (Preprocessing LLM)
# ==========================================
@lru_cache()
def get_preprocessing_llm() -> ChatOpenAI:
    """
    获取用于文本分块预处理的 LLM 客户端单例。
    """
    return _create_chat_llm("preprocess", temperature=0)

# ==========================================
# 2. Embedding 模型 (Embedding Model)
# ==========================================
@lru_cache()
def get_embedding_model() -> OpenAIEmbeddings:
    """
    获取 Embedding 模型客户端单例。
    """
    # 1. 获取 Embedding 专用配置
    config = settings.get_llm_config_by_name("embedding")
    
    # 2. 实例化 OpenAIEmbeddings
    # 注意：OpenAIEmbeddings 的参数与 ChatOpenAI 略有不同
    return OpenAIEmbeddings(
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key
    )

# ==========================================
# 3. 查询重写 LLM (Rewrite LLM)
# ==========================================
@lru_cache()
def get_rewrite_llm() -> ChatOpenAI:
    """
    获取用于 Query Rewrite 的 LLM 客户端单例。
    """
    return _create_chat_llm("rewrite", temperature=0)

# ==========================================
# 4. research LLM
# ==========================================
@lru_cache()
def get_research_llm() -> ChatOpenAI:
    """
    获取用于 research 的 LLM 客户端单例。
    """
    return _create_chat_llm("research", temperature=0)

# ==========================================
# 5. Reranker 客户端 (TEI Reranker)
# ==========================================
@lru_cache()
def get_rerank_client() -> TEIRerankerClient:
    """
    获取 TEI Reranker 客户端单例。
    注：Reranker 配置结构特殊（包含 timeout 等），且通常不视为标准 LLM，
    因此这里直接访问 settings.tei_rerank 。
    """
    return TEIRerankerClient(
        base_url=settings.tei_rerank.base_url,
        api_key=settings.tei_rerank.api_key,
        timeout=settings.tei_rerank.timeout,
        max_concurrency=settings.tei_rerank.max_concurrency
    )