from functools import lru_cache
import json
import json_repair
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.callbacks import adispatch_custom_event
# 引入 RunnableConfig
from langchain_core.runnables import RunnableConfig

from ..llm.factory import get_research_llm
from .states import WorkerState, TaskResult
from .utils import fetch_rag_context
# 引入新提取的提示词模块
from .prompt.worker_prompt import WORKER_SUMMARIZATION_TEMPLATE, WORKER_SYSTEM_PROMPT
from .utils import construct_messages_with_fallback

# ==========================================
# 节点函数 (Node Functions)
# ==========================================

async def search_node(state: WorkerState, config: RunnableConfig) -> Dict[str, Any]:
    """Worker 搜索节点"""
    task = state["task"]
    
    # 使用 adispatch_custom_event 发送实时事件
    await adispatch_custom_event(
        "worker_progress", 
        {
            "task_id": task.id,
            "title": task.title,
            "status": "researching",
            "message": f"正在研究 {task.title} 任务..."
        },
        config=config # 透传 config
    )
    
    # 执行异步搜索
    search_results = await fetch_rag_context(task.query)
    
    return {"raw_data": search_results}

async def summarize_node(state: WorkerState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Worker 节点的总结步骤。
    利用 LLM 阅读搜索结果，根据任务意图生成详细报告和摘要。
    """
    task = state["task"]
    raw_data_list = state.get("raw_data", [])

    # 1. 构建带有索引的上下文
    # 格式：--- 资料 1 (来源: arXiv_2309.1234.pdf) ---
    context_segments = []
    references = set()
    
    for idx, item in enumerate(raw_data_list, 1):
        content = item.get("content", "").strip()
        source = item.get("document_name", "未知来源")
        
        # 过滤无效内容
        if content and content != "未找到相关资料" and len(content) > 10:
            segment = f"--- 资料 {idx} (来源: {source}) ---\n{content}"
            context_segments.append(segment)
            references.add(source)
    
    if not context_segments:
        context_text = "未检索到有效信息。"
    else:
        context_text = "\n\n".join(context_segments)

    context_vars = {
        "title": task.title,
        "intent": task.intent,
        "context_text": context_text
    }

    # 构建最终 User Prompt
    messages, langfuse_prompt_obj = construct_messages_with_fallback("worker/worker-summarization", context_vars)
    
    if messages is None:
        # 使用 prompts 模块中的模板进行格式化
        prompt = WORKER_SUMMARIZATION_TEMPLATE.format(
            title=task.title,
            intent=task.intent,
            context_text=context_text
        )

        messages = [
            SystemMessage(content=WORKER_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ]

    try:
        llm = get_research_llm()
        # 将 prompt 对象注入 config
        # 确保 config metadata 存在
        if config is None: config = {}
        if "metadata" not in config: config["metadata"] = {}
        
        # 如果成功获取到了 langfuse 对象，注入它
        if langfuse_prompt_obj:
            config["metadata"]["langfuse_prompt"] = langfuse_prompt_obj
        # 透传 config
        response = await llm.ainvoke(messages, config=config)
        result_text = response.content.strip()
        
        # 使用 json_repair 解析
        parsed_data = json_repair.loads(result_text)
        
        content_raw = parsed_data.get("content", "生成内容失败")
        summary_raw = parsed_data.get("summary", "生成摘要失败")

        # 容错处理
        if isinstance(content_raw, (dict, list)):
            content = json.dumps(content_raw, ensure_ascii=False, indent=2)
        else:
            content = str(content_raw)

        if isinstance(summary_raw, (dict, list)):
            summary = json.dumps(summary_raw, ensure_ascii=False, indent=2)
        else:
            summary = str(summary_raw)

    except Exception as e:
        content = str(e)
        summary = "生成出错"

    # 3. 构建最终结果对象
    final_task_result = TaskResult(
        task_id=task.id,
        title=task.title,
        content=content,
        summary=summary,
        references=list(references)
    )

    # 发送完成事件
    log_msg = f"{task.title}任务已研究完成：（{summary}）"
    
    await adispatch_custom_event(
        "worker_progress", 
        {
            "task_id": task.id,
            "title": task.title,
            "status": "completed",
            "message": log_msg,
            "summary": summary
        },
        config=config
    )

    return {"final_result": final_task_result}

# ==========================================
# 4. 图构建
# ==========================================
@lru_cache
def get_worker_agent():
    worker_builder = StateGraph(WorkerState)
    worker_builder.add_node("search", search_node)
    worker_builder.add_node("summarize", summarize_node)
    worker_builder.add_edge(START, "search")
    worker_builder.add_edge("search", "summarize")
    worker_builder.add_edge("summarize", END)
    return worker_builder.compile()