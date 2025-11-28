import uvicorn
import shutil
import uuid
import os
import asyncio 
import aiofiles
import json
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# 导入服务接口定义和请求模型 (注意别名，避免混淆)
from ..services.agent_service import AgentService, ReportRequest as ServiceReportRequest
from ..domain.models import DocumentSource
from ..domain.interfaces import Ingestor
# 导入工厂方法
from ..services.factory import get_agent_service, get_ingestion_service
# 导入 API 层定义的 Schema
from .schemas import ResearchRequest, ReviewRequest

app = FastAPI(title="Research Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. DeepResearch 服务接口
# ==========================================

@app.post("/api/research/start")
async def start_research(req: ResearchRequest):
    """
    启动任务接口
    """
    return {"status": "ready", "thread_id": req.thread_id}

@app.get("/api/research/stream/{thread_id}")
async def stream_research(
    thread_id: str, 
    goal: str,
    service: AgentService = Depends(get_agent_service)
):
    """
    SSE 流式输出接口
    """
    # 构造 ServiceReportRequest 对象
    # 不再直接传 input_data，而是传封装好的 request 对象
    service_request = ServiceReportRequest(
        report_id=thread_id,
        query=goal,
        action="start"
    )
    
    return StreamingResponse(
        service.generate_report(service_request),
        media_type="text/event-stream"
    )

@app.post("/api/research/review")
async def review_plan(
    req: ReviewRequest,
    service: AgentService = Depends(get_agent_service)
):
    """
    人工审核接口
    """
    if req.action not in ["approve", "revise"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    # 构造 ServiceReportRequest 对象 (Resume 模式)
    service_request = ServiceReportRequest(
        report_id=req.thread_id,
        action=req.action, 
        feedback=req.feedback,
        query=None # 恢复阶段通常不需要 query
    )

    return StreamingResponse(
        service.generate_report(service_request),
        media_type="text/event-stream"
    )

# ==========================================
# 2. 文档上传与解析接口
# ==========================================
UPLOAD_DIR = "uploads"
# 限制最大文件大小 (100MB)
MAX_FILE_SIZE_MB = 100
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 辅助函数：异步保存文件
async def save_upload_file_async(upload_file: UploadFile, destination: str):
    file_size = 0
    try:
        async with aiofiles.open(destination, 'wb') as out_file:
            while content := await upload_file.read(1024 * 1024):  # 每次读取 1MB
                file_size += len(content)
                
                # Check: 如果超过最大限制
                if file_size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413, # Payload Too Large
                        detail=f"文件过大，超过限制 ({MAX_FILE_SIZE_MB}MB)"
                    )
                
                await out_file.write(content)
    except HTTPException:
        # 如果是大小超限触发的异常，抛出给上层
        # 在抛出前，必须删除这个只写了一半的垃圾文件
        if os.path.exists(destination):
            os.remove(destination)
        raise 
    except Exception as e:
        # 其他 IO 错误
        if os.path.exists(destination):
            os.remove(destination)
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")

@app.post("/api/ingest/upload")
async def upload_and_ingest_document(
    file: UploadFile = File(...),
    ingestion_service: Ingestor = Depends(get_ingestion_service)
):
    """
    上传文件并触发解析流程，实时流式返回解析日志。
    """
    # 1. 准备路径
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
        
    safe_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # 2. 异步保存文件，避免阻塞主线程
    await save_upload_file_async(file, file_path)

    # 3. 创建 DocumentSource 对象
    source = DocumentSource(
        file_path=file_path,
        document_name=file.filename,
        document_id=str(uuid.uuid4())
    )

    # 4. 定义流式生成器
    async def ingestion_stream_generator():
        queue = asyncio.Queue()
        STOP_SIGNAL = object()

        async def status_callback(msg: str):
            # 构造标准的 SSE 格式
            sse_msg = f"event: log\ndata: {json.dumps({'message': msg}, ensure_ascii=False)}\n\n"
            await queue.put(sse_msg)

        async def run_pipeline():
            try:
                await status_callback(f"文件: {file.filename} 上传成功，开始解析...")
                await ingestion_service.pipeline(source, status_callback)
                await status_callback("✅ 解析流程完成。")
            except Exception as e:
                error_data = json.dumps({'error': str(e)}, ensure_ascii=False)
                await queue.put(f"event: error\ndata: {error_data}\n\n")
            finally:
                await queue.put(STOP_SIGNAL)

        # 启动后台任务
        task = asyncio.create_task(run_pipeline())

        try:
            while True:
                data = await queue.get()
                if data is STOP_SIGNAL:
                    break
                yield data
        except asyncio.CancelledError:
            # 如果前端断开连接（比如用户刷新页面），取消后台任务
            task.cancel()
            raise

    return StreamingResponse(
        ingestion_stream_generator(),
        media_type="text/event-stream",
        # 防止 Nginx 等代理服务器缓存流式响应
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"} 
    )

if __name__ == "__main__":
    uvicorn.run("src.backend.api.server:app", host="0.0.0.0", port=8000, reload=True)