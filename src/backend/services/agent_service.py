import json
import traceback
from typing import AsyncGenerator, Optional, Dict, Any
from langgraph.types import Command

# 导入获取图的方法
from ..infrastructure.agents.orchestrator_agent import get_orchestrator_graph
from ..domain.interfaces import AgentService
from ..domain.models import ReportRequest

class AgentServiceImpl(AgentService):
    def __init__(self):
        # 初始化图实例
        self.graph = get_orchestrator_graph()

    async def generate_report(self, request: ReportRequest) -> AsyncGenerator[str, None]:
        """
        实现 generate_report 接口。
        根据 request.action 决定是启动新任务还是恢复中断的任务。
        """
        thread_id = request.report_id
        input_data = None
        resume_command = None

        # 1. 构建输入参数
        if request.action == "start":
            if not request.query:
                # 如果是开始请求，必须要有 query
                yield f"event: error\ndata: {json.dumps({'error': 'Start action requires a query'})}\n\n"
                return

            input_data = {
                "goal": request.query,
                "plan": [],
                "results": [],
                "loop_count": 0,
                "user_feedback": None,
                "reflection_feedback": None,
                "final_report": ""
            }
        
        elif request.action == "approve":
            resume_command = Command(resume={"action": "approve"})
            
        elif request.action == "revise":
            resume_command = Command(resume={"action": "revise", "feedback": request.feedback})

        # 2. 调用核心流生成逻辑
        # 复用原 event_stream_generator 的逻辑，但现在它是内部实现细节
        async for event in self._run_graph_stream(thread_id, input_data, resume_command):
            yield event

    async def _run_graph_stream(
        self, 
        thread_id: str, 
        input_data: Optional[Dict[str, Any]] = None, 
        resume_command: Optional[Command] = None
    ) -> AsyncGenerator[str, None]:
        """
        内部方法：执行 Graph 并生成 SSE 格式的流。
        """
        config = {"configurable": {"thread_id": thread_id}}

        try:
            # 决定是启动新任务还是恢复中断
            if resume_command:
                async_generator = self.graph.astream_events(resume_command, config, version="v2")
            else:
                async_generator = self.graph.astream_events(input_data, config, version="v2")

            async for event in async_generator:
                kind = event["event"]
                
                # 1. 处理 LLM 流式输出 (Writer 节点)
                if kind == "on_chat_model_stream" and event["metadata"].get("langgraph_node") == "writer":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield f"event: report_token\ndata: {json.dumps({'token': chunk.content})}\n\n"

                # 2. 处理通用日志事件 (Agent Log)
                elif kind == "on_custom_event" and event["name"] == "agent_log":
                    yield f"event: log\ndata: {json.dumps(event['data'])}\n\n"
                
                # 3. 处理 Worker 进度事件
                elif kind == "on_custom_event" and event["name"] == "worker_progress":
                    yield f"event: progress\ndata: {json.dumps(event['data'])}\n\n"

            # 循环结束，检查最终状态或中断
            snapshot = await self.graph.aget_state(config)
            
            # Debug log
            print(f"Snapshot next: {snapshot.next}")
            
            if snapshot.next:
                # 尝试提取中断信息
                interrupt_value = None
                if snapshot.tasks:
                    for task in snapshot.tasks:
                        if task.interrupts:
                            interrupt_value = task.interrupts[0].value
                            break
                
                if interrupt_value:
                    yield f"event: interrupt\ndata: {json.dumps(interrupt_value)}\n\n"
                else:
                    # 异常中断状态：有 next 但无 interrupt 信息
                    yield f"event: log\ndata: {json.dumps({'message': '⚠️ 系统暂停，但未检测到明确的中断信号，请检查后端日志。'})}\n\n"
            else:
                # 任务完成
                final_report = snapshot.values.get("final_report")
                if final_report:
                    yield f"event: done\ndata: {json.dumps({'report': final_report})}\n\n"
                else:
                    pass

        except Exception as e:
            print(f"Stream Error: {e}")
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
