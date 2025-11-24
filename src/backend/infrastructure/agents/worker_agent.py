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

    # 1. 构建上下文
    context_text = ""
    references = set()
    
    for idx, item in enumerate(raw_data_list, 1):
        content = item.get("content", "")
        source = item.get("document_name", "Unknown")
        if content and content != "未找到相关资料":
            context_text += f"--- 资料 {idx} (来源: {source}) ---\n{content}\n\n"
            references.add(source)
    
    if not context_text:
        context_text = "未检索到有效信息。"

    # 2. 调用 LLM 进行总结
    llm = get_research_llm()
    
    prompt = f"""
    你是一个专业的AI研究员。请根据以下背景资料完成研究任务。

    【任务信息】
    标题：{task.title}
    意图：{task.intent}

    【背景资料】
    {context_text}

    【要求】
    1. 请严格根据背景资料，详细回答任务意图所需要的内容。
    2. 在你撰写的研究报告中引用参考资料的位置保留参考资料的来源（文档名）。
    3. 输出必须包含两部分：
       - content: 研究意图对应的详细研究结果（必须是Markdown格式字符串，若有公式，则使用latex语法）。
       - summary: 对研究结果的一段简练的摘要（100字以内，必须是纯文本字符串）。
    4. 请严格按照以下 JSON 格式返回，不要包含 Markdown 代码块标记：
    {{
        "content": "这里填入你的研究结果...",
        "summary": "这里填入研究结果的摘要..."
    }}
    """

    messages = [
        SystemMessage(content="你是一个输出 JSON 格式的助手。"),
        HumanMessage(content=prompt)
    ]

    try:
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