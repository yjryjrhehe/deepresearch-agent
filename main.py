import uvicorn
import logging
from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from router import router

# 假设上一轮的 router 代码保存在 src/backend/api/routers/retrieval.py
# from src.backend.api.routers.retrieval import router as retrieval_router

# ==========================================
# 1. 定义健康检查的响应模型
# ==========================================
class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0" # 可以读取配置文件的版本号
    components: dict = {}  # 用于扩展显示组件状态 (如: {"database": "up"})

# ==========================================
# 2. 初始化 FastAPI 应用
# ==========================================
app = FastAPI(
    title="检索服务 API",
    description="RAG 检索服务与 Agent 接口",
    version="0.1.0"
)

# 配置 CORS (根据实际需求调整)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 3. 注册业务路由
# ==========================================
app.include_router(router)

# ==========================================
# 4. 健康检查逻辑 (Health Check)
# ==========================================

@app.get(
    "/health",
    summary="服务健康检查",
    description="用于 K8s Liveness Probe 或负载均衡器检查服务存活状态",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["System"]
)
async def health_check():
    """
    基础存活检查。
    如果要扩展为“就绪检查”(Readiness Probe)，可以在这里尝试 ping 数据库。
    """
    # TODO: 如果需要深度检查，可以在这里调用 database.ping() 或 factory.check_connections()
    # 如果关键组件挂了，可以返回 503 Service Unavailable
    
    return HealthResponse(
        status="ok", 
        components={
            "api_server": "running"
            # "opensearch": "unknown"  <-- 可以在此处扩展
        }
    )

# ==========================================
# 5. 启动入口
# ==========================================
if __name__ == "__main__":
    # 生产环境建议使用 log_config 配置文件
    logging.basicConfig(level=logging.INFO)
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True, # 开发模式开启热重载
        workers=1
    )