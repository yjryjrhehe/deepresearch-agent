from abc import ABC, abstractmethod
from typing import List, Optional, AsyncGenerator
from .models import DocumentSource, DocumentChunk, RetrievedChunk, ReportRequest, Report
import asyncio

# --------------------------------------------------------------------
# 1. 基础设施接口 (由 infrastructure/ 实现)
# --------------------------------------------------------------------


class DocumentParser(ABC):
    """
    对应"docling+VLM"。
    职责：将原始文件（PDF, DOCX等）解析为Markdown。
    """

    @abstractmethod
    async def parse(self, source: DocumentSource) -> str:
        """
        解析原始文档。
        :param source: DocumentSource对象，包含文件路径等信息。
        :return: Markdown 格式的字符串。
        """
        pass


class TextSplitter(ABC):
    """
    对应 "基于markdown结构分块" 和 "基于语义分块"。
    职责：将Markdown文本分割成 DocumentChunk。
    """

    @abstractmethod
    def split(
        self, markdown_content: str, source: DocumentSource
    ) -> List[DocumentChunk]:
        """
        将Markdown文本分割成块。
        :param markdown_content: 从 IDocumentParser 获得的Markdown内容。
        :param source: 原始文档信息，用于填充块的元数据。
        :return: DocumentChunk 列表 (此时还没有摘要和假设性问题)。
        """
        pass


class PreProcessor(ABC):
    """
    对切分后的文本块进行预处理，如生成摘要、假设性问题等。
    """

    @abstractmethod
    async def preprocess(self, chunk: DocumentChunk) -> List[DocumentChunk]:
        """
        将原始文本块转换为多个新的Document对象，便于检索。
        """
        pass
    
    @abstractmethod
    async def run_concurrent_preprocessing(
        self, chunks: List[DocumentChunk]
    ) -> List[DocumentChunk]:
        """
        在生产环境中并发处理所有文本块的主函数。
        :param chunks: 所有待处理的块列表。
        :return: 成功处理和扩充的块的列表。
        """
        pass


class SearchRepository(ABC):
    """
    对应 OpenSearch 的存储和检索抽象。
    由 infrastructure/repository/opensearch_store.py 实现。
    """

    @abstractmethod
    async def bulk_add_documents(self, chunks: List[DocumentChunk]):
        """
        批量添加（或更新）文档块到 OpenSearch。
        此方法内部应处理向量生成。
        """
        pass

    @abstractmethod
    async def hybrid_search(self, query_text: str, k: int = 5, rrf_k: int = 60):
        """
        执行混合检索。
        对应流程图2的 "检索、去重 (向量相似度+BM25)"。
        :param query: 单个子查询 (sub_query)。
        :return: 检索到的原始文档块列表（带search_score）。
        """
        pass

    @abstractmethod
    async def hybrid_search_batch(
        self, 
        queries: List[str], 
        k: int = 5, 
        rrf_k: int = 60
    ) -> List[List[RetrievedChunk]]:
        """
        批量执行混合检索。
        """
        pass


# class IMessageProducer(ABC):
#     """
#     消息队列生产者 (RabbitMQ) 的抽象。
#     由 infrastructure/messaging/producer.py 实现。
#     """
#     @abstractmethod
#     def publish(self, queue_name: str, message: BaseModel):
#         """向指定队列发布一条Pydantic消息"""
#         pass

# class IMessageConsumer(ABC):
#     """
#     消息队列消费者 (RabbitMQ) 的抽象。
#     由 infrastructure/messaging/consumer.py 实现。
#     """
#     @abstractmethod
#     def consume(self, queue_name: str, callback: Callable[[BaseModel], bool]):
#         """
#         订阅队列并用回调函数处理消息。
#         :param callback: 返回True表示ack，False表示nack。
#         """
#         pass


class ReportRepository(ABC):
    """
    用于存储和更新 Report 对象状态的仓库。
    (这可能是 OpenSearch, 也可能是另一个数据库如 PostgreSQL/MongoDB)。
    """

    @abstractmethod
    def create(self, report: Report):
        """创建一个新的报告记录"""
        pass

    @abstractmethod
    def get(self, report_id: str) -> Optional[Report]:
        """根据ID获取报告"""
        pass

    @abstractmethod
    def update(
        self, report_id: str, report: Report, error_message: Optional[str] = None
    ):
        """更新报告状态"""
        pass


# --------------------------------------------------------------------
# 2. 服务接口 (由 services/ 实现)
# --------------------------------------------------------------------


class Ingestor(ABC):
    """
    文档摄入服务 (业务流程编排)。
    services/ingestion_service.py
    """

    @abstractmethod
    async def pipeline(self, source: DocumentSource):
        """
        编排完整的文档摄入流程（流程图1）。
        1. 调用 DocumentParser
        2. 调用 TextSplitter
        3. 调用 Preprocessor
        4. 调用 SearchRepository.add_chunks
        """
        pass


class Retriever(ABC):
    """
    文档检索服务 (业务流程编排)。
    由 services/retrieval_service.py 实现。
    """

    @abstractmethod
    async def retrieve(self, query: str) -> List[RetrievedChunk]:
        """
        编排完整的RAG检索流程。
        1. 调用 rewrite_client
        2. 并发调用 SearchRepository.hybrid_search
        3. 并发调用 rerank_client
        4. 聚合、去重、返回最终的排序列表
        """
        pass


class AgentService(ABC):
    """
    报告生成智能体服务 (业务流程编排)。
    由 AgentServiceImpl 实现。
    """

    @abstractmethod
    async def generate_report(self, request: ReportRequest) -> AsyncGenerator[str, None]:
        """
        编排完整的报告生成流程。
        将graph封装进来，提取每一步的输出结果（yield），实现流式输出。
        """
        pass
