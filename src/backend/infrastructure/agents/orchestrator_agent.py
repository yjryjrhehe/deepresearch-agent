import asyncio
from typing import Literal
from functools import lru_cache

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, Send, interrupt
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
# 【修改】引入 RunnableConfig 用于传递运行上下文
from langchain_core.callbacks import adispatch_custom_event
from langchain_core.runnables import RunnableConfig

from .planner_agent import get_planner_agent
from .worker_agent import get_worker_agent
from .reflector_agent import get_reflector_agent
from ..llm.factory import get_research_llm
from .states import MainState
# 引入新提取的提示词模块
from .prompt.reporter_prompt import REPORT_WRITER_TEMPLATE
from .utils import construct_messages_with_fallback

# 初始化子图 (获取编译后的图实例)
planner_graph = get_planner_agent()
worker_graph = get_worker_agent()
reflector_graph = get_reflector_agent()


# 【修改】增加 config 参数
async def planner_adapter_node(state: MainState, config: RunnableConfig):
    """
    【适配器】调用 Planner 子图
    负责将主图状态转换为 Planner 子图所需的输入格式。
    """
    # 1. 准备子图输入
    sub_input = {
        "goal": state["goal"],
        "user_feedback": state.get("user_feedback"),
        "reflection_feedback": state.get("reflection_feedback"),
        "current_plan": state.get("plan", [])
    }
    
    # 2. 调用子图 (异步调用)
    # 【关键修改】透传 config，确保事件能冒泡
    output = await planner_graph.ainvoke(sub_input, config)

    # 【关键修改】发送日志时传入 config
    await adispatch_custom_event("agent_log", {"message": "研究大纲已规划完成"}, config=config)

    
    # 3. 处理输出并更新主图状态
    # 注意：生成新计划后，清空 feedback 标志，防止死循环
    return {
        "plan": output["final_plan"],
        "user_feedback": None,       # 清空已处理的用户反馈
        "reflection_feedback": None, # 清空已处理的反思反馈
        "loop_count": state.get("loop_count", 0) # 确保 loop_count 存在
    }

def human_review_node(state: MainState) -> Command[Literal["dispatch_node", "planner_agent"]]:
    """
    人工审核节点
    利用 LangGraph 的 interrupt 机制暂停执行，等待用户确认。
    """
    loop_count = state.get("loop_count", 0)
    
    # 如果是自动迭代 (loop > 0)，或者反思后的自动修正，跳过人工审核
    # 这里策略可调：是否每次修改都要人看？这里假设第一次需要人看，后续自动跑
    if loop_count > 0:
        return Command(goto="dispatch_node")
        
    current_plan = state["plan"]
    
    # 中断：将当前计划发送给前端/用户
    # interrupt 会暂停图的执行，直到通过 Command(resume=...) 恢复
    user_input = interrupt({
        "type": "plan_review",
        "data": [t.model_dump() for t in current_plan],
        "message": f"已生成 {len(current_plan)} 个研究任务，请审核。"
    })
    
    # 恢复后的逻辑 (user_input 是 resume 传入的数据)
    action = user_input.get("action")
    
    if action == "revise":
        # 用户要修改 -> 更新反馈 -> 回到 Planner Agent
        print(f"--- [Human] 用户要求修改计划: {user_input.get('feedback')}")
        return Command(
            update={"user_feedback": user_input.get("feedback")}, 
            goto="planner_agent" 
        )
    elif action == "approve":
        # 用户批准 -> 去分发
        print("--- [Human] 计划已批准")
        return Command(goto="dispatch_node")
    
    raise ValueError(f"Unknown action: {action}")

def dispatch_node(state: MainState):
    """
    过渡节点
    只负责占位，真正的分发逻辑在 conditional_edge (route_to_workers) 中。
    """
    return {} 

def route_to_workers(state: MainState):
    """
    路由函数：生成并行 Send 对象
    【关键逻辑】只分发那些还没有结果的任务（增量分发）
    """
    all_tasks = state.get("plan", [])
    existing_results = state.get("results", [])
    
    # 1. 获取已完成任务的 ID 集合
    completed_task_ids = set(r.task_id for r in existing_results)
    
    # 2. 过滤出未完成的任务
    # 只有 ID 不在结果集里的任务，才会被送去执行
    pending_tasks = [t for t in all_tasks if t.id not in completed_task_ids]
    
    if not pending_tasks:
        print("--- [System] 所有任务已完成，无新任务分发 ---")
        return [] # 返回空列表，意味着不执行任何 worker，直接流向下一个节点 (如果有 default edge)
        
    print(f"--- [System] 正在分发 {len(pending_tasks)} 个新任务 ---")
    
    # 使用 Send API 并行分发给 research_worker 节点
    # 注意：Send 的第一个参数是目标节点名称，第二个参数是传递给子图/节点的 state
    return [Send("research_worker", {"task": t}) for t in pending_tasks]

# 【修改】增加 config 参数
async def research_worker_adapter_node(state: dict, config: RunnableConfig):
    """
    【适配器】Worker 节点适配器
    
    作用：
    1. 接收 Send 传来的 payload ({"task": ...})
    2. 调用 Worker 子图
    3. 将子图结果 ({"final_result": ...}) 转换为 MainState 格式 ({"results": [...]})
    """
    # 调用 Worker 子图
    # 【关键修改】透传 config，确保 Worker 内部的进度事件能冒泡
    result_state = await worker_graph.ainvoke(state, config)
    
    # 提取结果并适配 MainState
    final_res = result_state.get("final_result")
    
    if final_res:
        # 返回列表以配合 operator.add
        return {"results": [final_res]}
    
    return {}

# 【修改】增加 config 参数
async def reflector_adapter_node(state: MainState, config: RunnableConfig):
    """
    【适配器】调用 Reflector 子图
    评估研究结果的完整性。
    """
    # 【修改】传入 config
    await adispatch_custom_event("agent_log", {"message": "正在进行反思..."}, config=config)

    sub_input = {
        "goal": state["goal"], 
        "results": state["results"]
    }
    
    # 使用导入的 reflector_graph，并透传 config
    output = await reflector_graph.ainvoke(sub_input, config)
    
    new_loop_count = state["loop_count"] + 1
    
    print(f"--- [Reflector] 评估结果: 足以生成报告? {output['is_sufficient']}")

    is_sufficient = output["is_sufficient"]
    gap = output["knowledge_gap"]

    # 【新增】发送反思结果日志
    if is_sufficient:
        log_msg = "反思结果：研究内容已覆盖研究目标，可以进行报告撰写。"
    else:
        log_msg = f"反思结果：研究结果尚有“{gap}”不足，正在重新规划大纲。"
    
    # 【修改】传入 config
    await adispatch_custom_event("agent_log", {"message": log_msg}, config=config)

    if not is_sufficient and new_loop_count < 3:
        return {
            "reflection_feedback": gap,
            "loop_count": new_loop_count
        }
    else:
        return {
            "reflection_feedback": None,
            "loop_count": new_loop_count
        }

def check_loop_condition(state: MainState):
    """
    条件边逻辑
    根据 Reflector 的反馈决定是回炉重造还是写报告。
    """
    if state.get("reflection_feedback"):
        return "planner_agent" # 回去重新规划
    return "writer"

# 【修改】增加 config 参数
async def report_node(state: MainState, config: RunnableConfig):
    """
    最终报告生成节点
    【关键】这里使用 ainvoke，但在 Server 端通过 astream_events 
    过滤 on_chat_model_stream 事件来实现前端的打字机效果。
    """
    # 【修改】传入 config
    await adispatch_custom_event("agent_log", {"message": "正在撰写研究报告..."}, config=config)

    print("--- [Writer] 正在撰写最终报告 ---")
    
    
    # 1. 组织输入数据
    # 使用明确的文本分隔符，指示 LLM 这是原始素材
    results_text = ""
    for r in state.get("results", []):
        results_text += f"【子任务研究结果：{r.title}】\n{r.content}\n\n"

    context_vars = {
        "goal": state.get('goal', '未命名主题'),
        "results_text": results_text
    }

    # 构建最终 User Prompt
    messages, langfuse_prompt_obj = construct_messages_with_fallback("reporter/reporter-prompt", context_vars)
    if messages is None:
        # 使用 prompts 模块中的模板进行格式化
        prompt = REPORT_WRITER_TEMPLATE.format(
            goal=state.get('goal', '未命名主题'),
            results_text=results_text
        )
        
        messages = [HumanMessage(content=prompt)]

    # LangGraph 的 astream_events 会自动捕获内部的流
    # 【修改】透传 config，确保流式事件能被捕获
    try:
        llm = get_research_llm()
        # 将 prompt 对象注入 config
        # 确保 config metadata 存在
        if config is None: config = {}
        if "metadata" not in config: config["metadata"] = {}
        
        # 如果成功获取到了 langfuse 对象，注入它
        if langfuse_prompt_obj:
            config["metadata"]["langfuse_prompt"] = langfuse_prompt_obj
        response = await llm.ainvoke(messages, config)
        
        return {"final_report": response.content}
    except Exception as e:
        print(f"撰写报告过程中发生错误：{e}")

# ==========================================
# 4. 图构建 (Graph Construction)
# ==========================================
@lru_cache
def get_orchestrator_graph():
    builder = StateGraph(MainState)

    builder.add_node("planner_agent", planner_adapter_node) 
    builder.add_node("human_review", human_review_node)
    builder.add_node("dispatch_node", dispatch_node)
    builder.add_node("research_worker", research_worker_adapter_node)
    builder.add_node("reflector", reflector_adapter_node)
    builder.add_node("writer", report_node)

    # 连线
    builder.add_edge(START, "planner_agent")
    builder.add_edge("planner_agent", "human_review")

    # 从 dispatch_node 出来的条件边：执行并行分发
    builder.add_conditional_edges(
        "dispatch_node",
        route_to_workers,
        ["research_worker"]
    )

    builder.add_edge("research_worker", "reflector")

    builder.add_conditional_edges(
        "reflector", 
        check_loop_condition, 
        {
            "planner_agent": "planner_agent",
            "writer": "writer"
        }
    )

    builder.add_edge("writer", END)

    memory = InMemorySaver()
    main_graph = builder.compile(checkpointer=memory)
    return main_graph

# ==========================================
# 5. 模拟运行与测试 (Simulation)
# ==========================================

async def main():
    main_graph = get_orchestrator_graph()
    print(">>> 启动 Orchestrator Agent 测试...")
    print(">>> 注意：此测试脚本依赖于完整的包结构 (.planner_agent 等)，建议使用 python -m agents.orchestrator_agent 运行")
    
    # 配置线程 ID，用于记忆上下文
    config = {"configurable": {"thread_id": "test_thread_001"}}
    
    initial_state = {
        "goal": "调研时空网格编码技术",
        "plan": [],
        "results": [],
        "loop_count": 0,
        "user_feedback": None,
        "reflection_feedback": None,
        "final_report": ""
    }
    
    print(f"\n[System] 初始目标: {initial_state['goal']}")

    # 1. 第一次运行：应该运行到 human_review 并暂停
    # 使用 astream 观察过程
    print("\n--- 阶段 1: 生成计划 ---")
    async for event in main_graph.astream(initial_state, config):
        # 打印节点产生的更新
        for node, patch in event.items():
            print(f"Nodes {node} finished.")
            if node == "planner_agent":
                print(f"生成的计划: {[t.title for t in patch['plan']]}")

    # 2. 检查中断状态
    snapshot = await main_graph.aget_state(config)
    if snapshot.next:
        print(f"\n[System] 流程已暂停，等待人工操作。当前节点: {snapshot.next}")
        
        # 获取中断时的 payload
        if snapshot.tasks:
            interrupt_value = snapshot.tasks[0].interrupts[0].value
            print(f"[UI 模拟] 收到请求: {interrupt_value['message']}")
            print(f"[UI 模拟] 计划内容: {len(interrupt_value['data'])} 个任务")

        # 模拟用户操作：批准 (Approve)
        print("\n[User] 用户点击了 '批准' 按钮...")
        resume_command = Command(resume={"action": "approve"})
        
        print("\n--- 阶段 2: 执行研究与报告 ---")
        # 继续运行
        async for event in main_graph.astream(resume_command, config):
            for node, patch in event.items():
                print(f"Nodes {node} finished.")
                if node == "research_worker":
                    res = patch.get("final_result")
                    if res:
                        print(f"  >> Worker 完成任务: {res.title}")

    # 3. 查看最终结果
    final_snapshot = await main_graph.aget_state(config)
    report = final_snapshot.values.get("final_report")
    
    if report:
        print("\n================ 最终报告 ================")
        print(report[:500] + "..." if len(report) > 500 else report)
        print("==========================================")
        # 【新增】将报告写入本地文件
        filename = "final_report.md"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"\n[System] 报告已成功写入本地文件: {filename}")
        except Exception as e:
            print(f"\n[Error] 写入文件失败: {e}")

    else:
        print("\n[Warning] 未生成报告，可能在反思循环中。")

if __name__ == "__main__":
    asyncio.run(main())