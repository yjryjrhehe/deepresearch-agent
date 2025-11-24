from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional

# ==========================================
# 1. 模拟导入 (根据你的实际项目结构调整)
# ==========================================
# 假设 DocumentChunk 在 domain.models 中定义，并且也是一个 Pydantic BaseModel
# 如果它只是普通类，你需要为它编写对应的 Pydantic Schema 以便 FastAPI 序列化

from src.backend.domain.models import RetrievedChunk, DocumentChunk
from src.backend.services.factory import get_retrieval_service
from src.backend.domain.interfaces import Retriever


# ==========================================
# 2. 定义 API Schemas (请求/响应模型)
# ==========================================

class RetrievalRequest(BaseModel):
    """
    检索接口请求参数
    """
    query: str = Field(..., min_length=1, description="用户的自然语言查询语句", example="如何配置 OpenSearch 的混合检索？")

# ==========================================
# 3. 定义 Router
# ==========================================

router = APIRouter(
    prefix="/retrieval",
    tags=["Retrieval Service"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/search",
    summary="执行 RAG 文档检索",
    description="包含查询改写、混合检索(Hybrid Search)、去重以及重排序(Rerank)的完整流程。",
    response_model=List[RetrievedChunk],
    status_code=status.HTTP_200_OK
)
async def search_knowledge_base(
    request: RetrievalRequest,
    # 使用 Depends 注入依赖，FastAPI 会自动调用 get_retrieval_service 获取实例
    retrieval_service: Retriever = Depends(get_retrieval_service)
):
    """
    核心检索接口
    - Input: 用户查询 (query)
    - Output: 排序后的文档块列表 (List[RetrievedChunk])
    """
    try:
        # 调用 Service 层的 retrieve 方法
        results = await retrieval_service.retrieve(query=request.query)
        
        if not results:
            # 或者是返回空列表，取决于你的前端需求。这里选择返回空列表。
            return []
            
        return results

    except Exception as e:
        # 捕获预期外的异常并返回 500
        # 实际项目中建议记录具体日志
        import logging
        logging.error(f"Retrieval API Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检索服务执行失败: {str(e)}"
        )