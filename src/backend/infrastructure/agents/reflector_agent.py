from functools import lru_cache
import json_repair
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.callbacks import adispatch_custom_event
# 引入 RunnableConfig
from langchain_core.runnables import RunnableConfig

from .states import ReflectionState
from ..llm.factory import get_research_llm


async def reflection_reasoning_node(state: ReflectionState, config: RunnableConfig) -> Dict[str, Any]:
    """
    反思节点的核心逻辑。
    调用 LLM 评估当前收集到的所有研究结果是否足以覆盖研究目标。
    """
    # 发送日志
    await adispatch_custom_event("agent_log", {"message": "正在评估研究深度与完整性..."}, config=config)
    
    goal = state["goal"]
    results = state["results"]

    # 如果没有结果，直接判定为不足
    if not results:
        return {
            "is_sufficient": False,
            "knowledge_gap": "尚未执行任何研究任务，缺乏所有必要信息。"
        }

    # 排序并构建上下文
    sorted_results = sorted(results, key=lambda r: r.task_id or 0)

    context_list = []
    for r in sorted_results:
        context_list.append(f"【任务ID: {r.task_id} | 任务题目: {r.title}】\n结果摘要: {r.summary}\n")
    
    context_str = "\n".join(context_list)
    
    llm = get_research_llm()

    prompt = f"""
    你是一个严格的研究评估专家。请根据总体研究目标，结合已完成的各子任务题目及其研究摘要，评估研究是否已达成目标。

    【总体研究目标】
    {goal}

    【已完成的任务与结果摘要】
    {context_str}

    【评估任务】
    请仔细分析上述“已完成的任务”与“结果摘要”，判断它们是否已经提供了充足的信息，可以支持撰写一份深度、全面的研究报告来回答“总体研究目标”。
    
    判别标准：
    1. 覆盖度：已完成的任务题目是否覆盖了总体目标的所有关键维度？
    2. 深度：结果摘要中的信息是否足够深入，还是仅流于表面？
    3. 证据：是否有具体的数据或案例支持？

    【输出要求】
    请严格按照以下 JSON 格式返回结果，不要包含 Markdown 标记：
    {{
        "is_sufficient": true 或 false,
        "knowledge_gap": "如果 is_sufficient 为 false，请简明扼要地描述缺少的关键视角、数据或具体案例（50字以内）。如果为 true，请填空字符串。"
    }}
    """

    messages = [
        SystemMessage(content="你是一个输出 JSON 格式的研究评估助手。"),
        HumanMessage(content=prompt)
    ]

    try:
        # 异步调用 LLM
        response = await llm.ainvoke(messages, config=config)
        result_text = response.content.strip()

        # 使用 json_repair 进行鲁棒解析
        parsed_data = json_repair.loads(result_text)
        
        is_sufficient = parsed_data.get("is_sufficient", False)
        knowledge_gap = parsed_data.get("knowledge_gap", "无法解析评估结果，建议补充研究。")

        # 类型安全检查
        if not isinstance(is_sufficient, bool):
            if str(is_sufficient).lower() == 'true':
                is_sufficient = True
            else:
                is_sufficient = False
        
        knowledge_gap = str(knowledge_gap)

    except Exception as e:
        print(f"Reflection failed: {e}")
        is_sufficient = False
        knowledge_gap = f"评估过程发生错误: {str(e)}"

    status_msg = "全部研究已完成，开始撰写研究报告。" if is_sufficient else f"研究内容存在不足: {knowledge_gap}，重新进行任务规划。"
    
    # 发送日志
    await adispatch_custom_event("agent_log", {"message": f"评估完成 - {status_msg}"}, config=config)

    return {
        "is_sufficient": is_sufficient,
        "knowledge_gap": knowledge_gap
    }

# ==========================================
# 4. 图构建 (Graph Construction)
# ==========================================
@lru_cache
def get_reflector_agent():
    reflector_builder = StateGraph(ReflectionState)
    reflector_builder.add_node("reflect", reflection_reasoning_node)
    reflector_builder.add_edge(START, "reflect")
    reflector_builder.add_edge("reflect", END)

    reflector_graph = reflector_builder.compile()
    return reflector_graph