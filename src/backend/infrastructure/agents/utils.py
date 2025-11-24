from typing import List
from .states import RawSearchResult
from ..repository.factory import get_retrieval_service

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