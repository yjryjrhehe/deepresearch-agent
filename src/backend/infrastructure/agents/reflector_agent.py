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
# 引入新提取的提示词模块
from .prompt.reflector_prompt import REFLECTION_SYSTEM_PROMPT, REFLECTION_EVALUATION_TEMPLATE
from .utils import construct_messages_with_fallback

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

    context_vars = {
        "goal": goal,
        "context_str": context_str
    }
    
    # 构建最终 User Prompt
    messages, langfuse_prompt_obj = construct_messages_with_fallback("reflector/reflector-evaluation", context_vars)

    if messages is None:
        # 使用 prompts 模块中的模板进行格式化
        prompt = REFLECTION_EVALUATION_TEMPLATE.format(
            goal=goal,
            context_str=context_str
        )

        messages = [
            SystemMessage(content=REFLECTION_SYSTEM_PROMPT),
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