from functools import lru_cache
import json
import json_repair
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
# 引入必要的运行配置和回调
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import adispatch_custom_event

from ..llm.factory import get_research_llm
from .states import ResearchTask, PlannerState

# ==========================================
# 1. 核心 Planner Logic
# ==========================================

async def generate_plan_logic(state: PlannerState, config: RunnableConfig):
    """
    规划智能体逻辑：
    1. 判断当前是 [初始规划]、[用户修改] 还是 [反思追加]
    2. 构建对应的 Prompt
    3. 决定是覆盖旧计划还是追加新任务
    4. 重新分配 ID
    """
    goal = state["goal"]
    user_feedback = state.get("user_feedback")
    reflection_feedback = state.get("reflection_feedback")
    current_plan = state.get("current_plan", [])
    
    # 序列化当前计划供 Prompt 使用
    current_plan_data = [t.model_dump() for t in current_plan]

    # --- 逻辑分支判断 ---
    is_incremental = False 
    
    # 基础 System Prompt
    system_prompt = """你是一名专业的'研究规划智能体'。
        ### 输出格式
        请输出一个标准的 JSON 列表 (Array)，包含以下字段：
        {
            "title": "<任务标题>",
            "intent": "<任务目的>",
            "query": "<搜索查询词>"
        }"""

    if user_feedback:
        # [模式 A: 用户修改] -> 全量重写
        log_msg = "检测到用户反馈，进入 [全量重写模式]..."
        is_incremental = False
        specific_instruction = f"""
            用户对现有计划提出了修改意见。
            请根据**用户反馈**，参考现有计划，**重新生成一份完整的、经过修正的研究任务列表**。
            你可以修改、删除旧任务或添加新任务。
            """
    elif reflection_feedback:
        # [模式 B: 反思迭代] -> 增量追加
        log_msg = "检测到反思反馈，进入 [增量追加模式]..."
        is_incremental = True
        specific_instruction = f"""
            之前的研究存在缺失信息。
            请根据**反思结果**，生成**需要补充的新任务**。
            **注意**：
            1. 仅输出新增的任务列表。
            2. **绝对不要**重复输前端现有计划中已有的任务。
            """
    else:
        # [模式 C: 初始规划] -> 全量生成
        log_msg = "开始进行初始研究任务规划..."
        is_incremental = False
        specific_instruction = f"""
            这是一个新的研究目标。请生成一份完整的初始研究任务列表（通常3-5个关键任务）。
            """

    # 发送日志事件
    await adispatch_custom_event("agent_log", {"message": log_msg}, config=config)

    # 构建最终 User Prompt
    user_prompt_content = f"""
            ### 上下文信息
            1. **研究目标**: {goal}
            2. **当前已有计划**: {json.dumps(current_plan_data, ensure_ascii=False)}
            3. **用户反馈**: {user_feedback if user_feedback else "无"}
            4. **反思结果**: {reflection_feedback if reflection_feedback else "无"}

            ### 指令
            {specific_instruction}

            请生成任务列表 JSON：
            """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt_content)
    ]

    # --- 调用 LLM ---
    try:
        llm = get_research_llm()
        # 透传 config 确保 trace 完整
        response = await llm.ainvoke(messages, config=config)
        content = response.content
        
        # --- 解析 JSON ---
        parsed_json = json_repair.loads(content)
        
        # 提取列表内容的通用容错逻辑
        if isinstance(parsed_json, dict):
            for key in ["tasks", "plan", "items", "result"]:
                if key in parsed_json and isinstance(parsed_json[key], list):
                    parsed_json = parsed_json[key]
                    break
        if not isinstance(parsed_json, list):
            parsed_json = []

        # --- 合并策略 ---
        
        final_data_to_process = []

        if is_incremental:
            # 增量模式：保留旧计划 + 追加新生成的计划
            await adispatch_custom_event("agent_log", {"message": f"保留原有 {len(current_plan_data)} 个任务，追加 {len(parsed_json)} 个新任务"}, config=config)
            final_data_to_process.extend(current_plan_data) # 先放旧的
            final_data_to_process.extend(parsed_json)       # 再放 LLM 新生成的
        else:
            # 全量模式：直接使用 LLM 生成的新列表替换旧列表
            final_data_to_process = parsed_json

        # --- 统一重新分配 ID ---
        final_plan_objects = []
        
        # 使用 enumerate 从 1 开始重新计数，确保 ID 连续且唯一
        for index, item in enumerate(final_data_to_process, start=1):
            try:
                task = ResearchTask(
                    id=index,  # <--- 强制重置 ID
                    title=str(item.get("title", "未命名")),
                    intent=str(item.get("intent", "")),
                    query=str(item.get("query", ""))
                )
                final_plan_objects.append(task)
            except Exception as e:
                print(f"跳过错误项: {e}")
                continue

        # ============================================================
        # 发送大纲结构日志给前端
        # ============================================================
        
        formatted_segments = []
        for task in final_plan_objects:
            segment = f"{task.id}. {task.title}"
            formatted_segments.append(segment)
        
        formatted_plan_string = "；".join(formatted_segments)
        
        await adispatch_custom_event(
            "agent_log", 
            {"message": f"规划完成，生成以下任务：{formatted_plan_string}"}, 
            config=config
        )
        
        return {"final_plan": final_plan_objects}

    except Exception as e:
        print(f"--- [Planner] Error: {e} ---")
        await adispatch_custom_event("agent_log", {"message": f"规划过程发生错误: {e}"}, config=config)
        return {"final_plan": state.get("current_plan", [])}

# ==========================================
# 2. 图构建
# ==========================================
@lru_cache
def get_planner_agent():
    planner_builder = StateGraph(PlannerState)
    planner_builder.add_node("generate", generate_plan_logic)
    planner_builder.add_edge(START, "generate")
    planner_builder.add_edge("generate", END)
    return planner_builder.compile()