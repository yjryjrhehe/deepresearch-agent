import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
import time

# --------------------------------------------------------------------
# 1. 文档摄入模型 (对应流程图1：文档解析和摄入)
# --------------------------------------------------------------------

class DocumentSource(BaseModel):
    """
    描述一个待处理的原始文档来源。
    在 ingestion_worker.py 中作为任务消息体。
    """
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="文档的唯一ID")
    file_path: Path = Field(..., description="文档在存储中的本地路径")
    
    # 1. 保持类型为 str，但设置 default=None
    #    这允许它在输入时缺失，并由下面的 'before' 验证器填充
    document_name: str = Field(
        default=None, 
        description="文档原始名称 (如果为 None，将自动从 file_path 提取)"
    )
    
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="其他元数据")

    @model_validator(mode='before')
    @classmethod
    def set_document_name_from_path(cls, data: Any) -> Any:
        """
        在字段验证之前，如果 document_name 未提供，则从 file_path 提取。
        """
        # 确保我们正在处理一个字典（即，不是从已实例化的对象创建）
        if isinstance(data, dict):
            
            # 2. 检查 document_name 是否未提供或明确为 None
            if data.get('document_name') is None:
                
                # 3. 检查 file_path 是否存在
                file_path_val = data.get('file_path')
                
                if file_path_val:
                    # 4. 从 file_path (可能是 str 或 Path) 提取 .name
                    #    因为这是 'before' 验证器, file_path_val 尚未被 Pydantic 转换为 Path 对象
                    if isinstance(file_path_val, str):
                        data['document_name'] = Path(file_path_val).name
                    elif isinstance(file_path_val, Path):
                        data['document_name'] = file_path_val.name
                    # (如果 file_path_val 是其他类型，让 Pydantic 在后续步骤中正常失败)
        
        return data


class DocumentChunk(BaseModel):
    """
    核心数据单元：文档块。
    对应流程图1中“存入opensearch”的最终数据结构。
    """
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="文本块的唯一ID")
    document_id: str = Field(..., description="所属文档的唯一ID")
    document_name: str = Field(..., description="文档原始名称")
    
    content: str = Field(..., description="文本块的原始内容")
    
    parent_headings: List[str] = Field(default_factory=list, description="所有父标题 (用于检索)")
    summary: Optional[str] = Field(None, description="AI生成的文本块摘要")
    hypothetical_questions: List[str] = Field(default_factory=list, description="AI生成的假设性问题 (用于增强检索)")
    
    # 注意：向量 (Vector) 本身通常不在Pydantic模型中传输，
    # 而是由 ISearchRepository 的实现在存入OpenSearch时生成和管理的。
    # 这里我们只定义业务数据。
    metadata: Dict[str, Any] = Field(default_factory=dict, description="其他元数据")


# --------------------------------------------------------------------
# 2. 检索模型 (对应流程图2：文档检索)
# --------------------------------------------------------------------

class RetrievedChunk(BaseModel):
    """
    从检索系统返回的带分数的文档块。
    """
    chunk: DocumentChunk = Field(..., description="检索到的原始文档块")
    
    # 对应流程图2中“检索”步骤的分数 (向量相似度+BM25)
    search_score: float = Field(..., description="混合检索的原始分数 (例如 BM25 + 向量相似度)")
    
    # 对应流程图2中 "rerank" 步骤的分数
    rerank_score: Optional[float] = Field(None, description="经过Reranker（如Cross-Encoder）重排后的分数")

class BatchRequestItem(BaseModel):
    """
    批量重排序请求的单项数据结构。
    
    [修改] texts 字段替换为 chunks，直接接收检索结果对象。
    """
    query: str = Field(..., description="用于检索或排序的查询文本")
    chunks: List[RetrievedChunk] = Field(..., description="待排序的检索结果列表")

# --------------------------------------------------------------------
# 3. 报告生成模型 (对应 Agent 和 API)
# --------------------------------------------------------------------

class ReportRequest(BaseModel):
    """
    API层 (reports.py) 接收的报告生成请求。
    也会由 agent_worker.py 消费。
    """
    query: str = Field(..., description="用户生成报告的原始查询")
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="报告的唯一ID (可由API端生成)")


class Report(BaseModel):
    """
    最终的“研究报告”领域对象。
    这将是 agent_service.py 的最终产出。
    """
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="报告的唯一ID")
    query: str = Field(..., description="生成报告的原始查询")
    content: Optional[str] = Field(None, description="最终生成的Markdown格式报告内容")
    error_message: Optional[str] = Field(None, description="如果失败，记录错误信息")
    
    # 最终用于生成报告的、经过Rerank和筛选的源数据块
    source_chunks: List[RetrievedChunk] = Field(default_factory=list, description="用于生成报告的引用来源")
    
    created_at: float = Field(default_factory=lambda: time.time(), description="报告创建时间戳")