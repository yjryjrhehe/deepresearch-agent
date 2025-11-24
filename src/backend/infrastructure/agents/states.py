import os
import json
import operator
import json_repair
from typing import Annotated, List, TypedDict, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# ==========================================
# 1. 共享数据模型 (Shared Schema)
# ==========================================

class ResearchTask(BaseModel):
    id: Optional[int] = Field(default=None, description="任务ID，用于前端排序")
    title: str = Field(description="任务标题")
    intent: str = Field(description="任务目的")
    query: str = Field(description="搜索查询词")

class TaskResult(BaseModel):
    task_id: int
    title: str = Field(description="任务标题")
    content: str = Field(description="搜索总结内容(当前任务研究结果)")
    summary: str = Field(description="当前研究任务研究结果摘要")
    references: List[str]= Field(description="来源链接")

# ==========================================
# 2. Planner Agent (规划智能体子图)
# ==========================================

class PlannerState(TypedDict):
    # 输入
    goal: str
    user_feedback: Optional[str]
    reflection_feedback: Optional[str]
    current_plan: List[ResearchTask]
    # 输出
    final_plan: List[ResearchTask]

# ==========================================
# 3. Worker Agent (执行智能体子图)
# ==========================================

# 定义单个检索结果的结构
class RawSearchResult(TypedDict):
    content: str
    document_name: str

class WorkerState(TypedDict):
    task: ResearchTask
    raw_data: List[RawSearchResult]
    final_result: Optional[TaskResult]

# ==========================================
# 4. Reflector Agent 状态定义
# ==========================================

class ReflectionState(TypedDict):
    """反思智能体的状态定义"""
    # 输入：总体研究目标
    goal: str
    # 输入：Worker Agent 产生的一系列结果
    results: List[TaskResult]
    
    # 输出：判断结果
    is_sufficient: bool
    knowledge_gap: str

# ==========================================
# 2. Orchestrator 状态定义
# ==========================================

class MainState(TypedDict):
    """主图状态"""
    goal: str
    # 计划列表
    plan: List[ResearchTask]
    # 结果列表：使用 operator.add 进行增量更新 (append)
    results: Annotated[List[TaskResult], operator.add]
    
    # 状态控制字段
    user_feedback: Optional[str]
    reflection_feedback: Optional[str]
    loop_count: int
    
    final_report: str