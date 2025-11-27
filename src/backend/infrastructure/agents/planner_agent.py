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
# 引入新提取的提示词模块
from .prompt.planner_prompt import PLANNER_SYSTEM_PROMPT, INSTRUCTION_INITIAL_PLAN, INSTRUCTION_REFLECTION_APPEND, INSTRUCTION_USER_MODIFICATION, USER_PROMPT_TEMPLATE 
from .utils import construct_messages_with_fallback

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
    
    # ------------------------------------------------------------------
    # 优化后的 System Prompt
    # ------------------------------------------------------------------
    system_prompt = PLANNER_SYSTEM_PROMPT

    if user_feedback:
        # [模式 A: 用户修改] -> 全量重写
        prompt_name = "planner/planner-modification"
        log_msg = "检测到用户反馈，进入 [大纲重构模式]..."
        is_incremental = False
        specific_instruction = INSTRUCTION_USER_MODIFICATION

    elif reflection_feedback:
        # [模式 B: 反思迭代] -> 增量追加
        prompt_name = "planner/planner-reflection"
        log_msg = "检测到反思反馈，进入 [增量补全模式]..."
        is_incremental = True
        specific_instruction = INSTRUCTION_REFLECTION_APPEND

    else:
        # [模式 C: 初始规划] -> 全量生成
        prompt_name = "planner/planner-initial"
        log_msg = "开始进行初始研究任务规划..."
        is_incremental = False
        specific_instruction = INSTRUCTION_INITIAL_PLAN

    # 发送日志事件
    await adispatch_custom_event("agent_log", {"message": log_msg}, config=config)

    context_vars = {
        "goal": goal,
        "current_plan_json": json.dumps(current_plan_data, ensure_ascii=False),
        "user_feedback": user_feedback if user_feedback else "无",
        "reflection_feedback": reflection_feedback if reflection_feedback else "无"
    }

    # 构建最终 User Prompt
    messages, langfuse_prompt_obj = construct_messages_with_fallback(prompt_name, context_vars)

    if messages is None:
        # --- Fallback: Langfuse 获取失败，使用本地模板 ---
        # 只有在 messages 为 None 时才执行本地构建逻辑
        user_prompt_content = USER_PROMPT_TEMPLATE.format(
            goal=goal,
            current_plan_json=json.dumps(current_plan_data, ensure_ascii=False),
            user_feedback=user_feedback if user_feedback else "无",
            reflection_feedback=reflection_feedback if reflection_feedback else "无",
            specific_instruction=specific_instruction
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt_content)
        ]

    # --- 调用 LLM ---
    try:
        llm = get_research_llm()
        # 将 prompt 对象注入 config
        # 确保 config metadata 存在
        if config is None: config = {}
        if "metadata" not in config: config["metadata"] = {}
        
        # 如果成功获取到了 langfuse 对象，注入它
        if langfuse_prompt_obj:
            config["metadata"]["langfuse_prompt"] = langfuse_prompt_obj
            
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