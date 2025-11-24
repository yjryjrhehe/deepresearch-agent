import uvicorn
import shutil
import uuid
import os
import asyncio 
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
# 路由定义
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
    # 【关键修复】构造 ServiceReportRequest 对象
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

    # 【关键修复】构造 ServiceReportRequest 对象 (Resume 模式)
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
# 新增：文档上传与解析接口 (修复后)
# ==========================================
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api/ingest/upload")
async def upload_and_ingest_document(
    file: UploadFile = File(...),
    ingestion_service: Ingestor = Depends(get_ingestion_service)
):
    """
    上传文件并触发解析流程，实时流式返回解析日志。
    """
    # 1. 保存文件到本地
    safe_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")

    # 2. 创建 DocumentSource 对象
    source = DocumentSource(
        file_path=file_path,
        document_name=file.filename,
        document_id=str(uuid.uuid4())
    )

    # 3. 定义流式生成器 (使用 Queue 模式)
    async def ingestion_stream_generator():
        # 创建一个异步队列
        queue = asyncio.Queue()
        
        # 定义停止信号 (Sentinel)
        STOP_SIGNAL = object()

        # 定义回调函数：这是一个普通异步函数，不再使用 yield
        async def status_callback(msg: str):
            # 将消息放入队列
            sse_msg = f"event: log\ndata: {json.dumps({'message': msg})}\n\n"
            await queue.put(sse_msg)

        # 封装业务逻辑的运行器
        async def run_pipeline():
            try:
                # 发送开始消息
                await status_callback(f"📥 文件 {file.filename} 上传成功，开始解析...")
                
                # 执行 pipeline
                # 注意：Service 内部可以放心地 await callback(...)
                await ingestion_service.pipeline(source, status_callback)
                
                # 成功完成消息
                await status_callback("✅ 解析流程完成。")
            except Exception as e:
                # 发送错误消息
                error_msg = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                await queue.put(error_msg)
            finally:
                # 无论成功失败，最后放入停止信号
                await queue.put(STOP_SIGNAL)

        # 在后台启动任务，不阻塞 yield 循环
        task = asyncio.create_task(run_pipeline())

        # 循环消费队列中的消息并 yield 给前端
        while True:
            # 等待队列中有新消息
            data = await queue.get()
            
            # 如果收到停止信号，跳出循环，结束流
            if data is STOP_SIGNAL:
                break
            
            # 将消息发送给前端
            yield data

    # 返回流式响应
    return StreamingResponse(
        ingestion_stream_generator(),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    uvicorn.run("src.backend.api.server:app", host="0.0.0.0", port=8000, reload=True)