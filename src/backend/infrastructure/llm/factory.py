from functools import lru_cache
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# 导入配置
from ...core.config import settings
# 导入自定义的 Reranker Client 类
from .reranker import TEIRerankerClient 

# ==========================================
# 1. 预处理 LLM (Preprocessing LLM)
# ==========================================
@lru_cache()
def get_preprocessing_llm() -> ChatOpenAI:
    """
    获取用于文本分块预处理的 LLM 客户端单例。
    """
    return ChatOpenAI(
        base_url=settings.preprocessing_llm.base_url,
        # 从 settings 读取 API Key
        api_key=settings.preprocessing_llm.api_key, 
        model=settings.preprocessing_llm.model,
        temperature=0,
        # 建议：如果并发高，可在此处设置 max_retries 等
        max_retries=3 
    )

# ==========================================
# 2. Embedding 模型 (Embedding Model)
# ==========================================
@lru_cache()
def get_embedding_model() -> OpenAIEmbeddings:
    """
    获取 Embedding 模型客户端单例。
    """
    return OpenAIEmbeddings(
        base_url=settings.embedding_llm.base_url,
        model=settings.embedding_llm.model,
        api_key=settings.embedding_llm.api_key,
        # 也可以从 settings 读取维度进行校验，或者传给 LangChain 
        # check_embedding_ctx_length=settings.embedding_llm.dimension
    )

# ==========================================
# 3. 查询重写 LLM (Rewrite LLM)
# ==========================================
@lru_cache()
def get_rewrite_llm() -> ChatOpenAI:
    """
    获取用于 Query Rewrite 的 LLM 客户端单例。
    """
    return ChatOpenAI(
        base_url=settings.rewrite_llm.base_url,
        api_key=settings.rewrite_llm.api_key,
        model=settings.rewrite_llm.model,
        temperature=0
    )

# ==========================================
# 4. Reranker 客户端 (TEI Reranker)
# ==========================================
@lru_cache()
def get_rerank_client() -> TEIRerankerClient:
    """
    获取 TEI Reranker 客户端单例。
    将配置参数注入到 Client 的 __init__ 中。
    """
    return TEIRerankerClient(
        base_url=settings.tei_rerank.base_url,
        api_key=settings.tei_rerank.api_key,
        timeout=settings.tei_rerank.timeout,
        max_concurrency=settings.tei_rerank.max_concurrency
    )