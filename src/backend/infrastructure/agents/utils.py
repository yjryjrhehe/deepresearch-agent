from typing import List, Any, Dict, Optional, Tuple
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
import logging

from ...core.config import settings
from ...core.logging import setup_logging
from .states import RawSearchResult
from ..repository.factory import get_retrieval_service
from ..langfuse.factory import init_langfuse_client


# === 日志配置 ===
setup_logging() 
logger = logging.getLogger(__name__)

async def fetch_rag_context(query: str) -> List[RawSearchResult]:
    """
    异步执行 RAG 检索并解析结果。
    
    Args:
        query (str): 搜索查询词。

    Returns:
        List[RawSearchResult]: 解析后的搜索结果列表。
    """
    extracted_results: List[RawSearchResult] = []

    try:
        # 1. 获取服务实例 (通常是单例或轻量级工厂)
        retrieval_service = get_retrieval_service()
        
        # 2. 调用搜索方法
        raw_results = await retrieval_service.retrieve(query)
        
        # 3. 适配结果格式
        if raw_results:
            for item in raw_results:
                chunk = getattr(item, "chunk", "")

                if chunk:
                    extracted_results.append({
                        "content": chunk.content,
                        "document_name": chunk.document_name
                    })

    except Exception as e:
        print(f"[Utils] Local Retrieval Service Error: {e}")
        # 可以在这里记录日志
        pass

    # 4. 处理空结果逻辑
    if not extracted_results:
        extracted_results.append({
            "content": "未找到相关资料",
            "document_name": "System"
        })
        
    return extracted_results


# ==========================================
# 0. Langfuse 初始化与辅助函数
# ==========================================

def convert_langfuse_msgs_to_langchain(messages: List[Dict[str, str]]) -> Optional[List[BaseMessage]]:
    """将 Langfuse 返回的 [{'role': 'user', ...}] 转换为 Langchain Message 对象"""
    lc_messages = []
    for msg in messages:
        if msg['role'] == 'system':
            lc_messages.append(SystemMessage(content=msg['content']))
        elif msg['role'] == 'user':
            lc_messages.append(HumanMessage(content=msg['content']))
        # 可以根据需要扩展 assistant 等其他角色
    return lc_messages

def construct_messages_with_fallback(
    prompt_name: str,
    context_vars: Dict[str, Any]
) -> Tuple[Optional[List[BaseMessage]], Optional[Any]]:
    """
    构建 Prompt 消息列表：优先使用 Langfuse，失败则回退到本地模板。
    """
    # 1. 尝试使用 Langfuse
    # 全局客户端实例 
    langfuse_client = init_langfuse_client(
        public_key=settings.langfuse.public_key,
        secret_key=settings.langfuse.secret_key,
        base_url=settings.langfuse.base_url
    )

    if langfuse_client:
        try:
            if prompt_name:
                # 获取 chat 类型的 prompt
                langfuse_prompt = langfuse_client.get_prompt(prompt_name, type="chat")
                # 编译 prompt (替换变量)
                compiled_msgs = langfuse_prompt.compile(**context_vars)
                # 转换为 Langchain 对象以保持下游兼容
                return convert_langfuse_msgs_to_langchain(compiled_msgs), langfuse_prompt
                
        except Exception as e:
            logger.error(f"从 Langfuse 获取 '{prompt_name}' Prompt 失败，回退到本地模式。Error: {e}")
            # 不抛出异常，继续执行下面的 Fallback 逻辑

    # 2. Fallback: 使用本地硬编码的 Prompt
    # 这是一个兜底策略，确保即使 Langfuse 挂了，系统也能运行
    logger.info(f"使用本地 Prompt 模板生成模式: {prompt_name}")
    return None, None