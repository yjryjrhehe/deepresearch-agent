import logging
from typing import List
import asyncio
import json_repair
from langchain_core.language_models import BaseChatModel

from .prompt.llm_chunk_preprocess_prompt import LLM_PREPROCESS_PROMPT
from ...domain.interfaces import PreProcessor
from ...domain.models import DocumentChunk
from ...core.logging import setup_logging

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)


class LLMPreprocessor(PreProcessor):
    """
    使用大语言模型（LLM）对文本块（DocumentChunk）进行预处理。

    该处理器的核心任务是调用LLM，为每个文本块生成
    内容摘要 (summary) 和 假设性问题 (hypothetical_questions)，
    并将这些生成的内容填充回原始的 DocumentChunk 对象中，
    以便后续用于增强检索（如向量检索和BM25混合检索）。
    """

    def __init__(self, llm: BaseChatModel, max_concurrency: int = 5):
        """
        初始化LLM预处理器。
        
        :param llm: 注入的 LLM 客户端实例 (依赖注入)
        :param max_concurrency: 最大并发数
        """
        # 依赖由外部注入，而不是自己创建
        self.llm = llm
        self.max_concurrency = max_concurrency
        
        log.info("LLMPreprocessor 初始化完成 (依赖已注入)。")

    async def preprocess(self, chunk: DocumentChunk) -> List[DocumentChunk]:
        """
        处理单个 DocumentChunk 对象，为其生成摘要和假设性问题。

        该方法实现了 PreProcessor 接口中的 process 抽象方法。

        Args:
            chunk (DocumentChunk): 待处理的文档块对象。

        Returns:
            List[DocumentChunk]:
                - 如果处理成功，返回一个列表，其中包含被扩充添加了summary和questions）的原始chunk对象 `[chunk]`。
                - 如果处理失败，返回一个空列表 `[]`。
        """
        try:
            # 1. 准备父标题字符串
            # 将父标题列表合并为单个字符串，用于提供上下文
            parent_title_str = " > ".join(chunk.parent_headings)

            # 2. 准备llm的输入
            prompt = LLM_PREPROCESS_PROMPT.format(
                parent_title=parent_title_str, doc=chunk.content
            )

            # 3. 调用LLM链
            # result 预期是一个字典, e.g., {"summary": "...", "questions": ["...", "..."]}
            result = await self.llm.ainvoke(prompt)
            result = json_repair.loads(result.content)

            # 4. 扩充（Enrich）原始的 DocumentChunk 对象
            chunk.summary = result.get("summary")
            chunk.hypothetical_questions = result.get("questions", [])

            log.debug(f"成功处理块 {chunk.chunk_id} (文档: {chunk.document_name})")

            # 5. 按接口要求返回列表
            return [chunk]

        except Exception as e:
            log.error(
                f"处理块 {chunk.chunk_id} (文档: {chunk.document_name}) 时失败: {e}"
            )
            # 发生错误时，返回空列表，表示此chunk处理失败
            return []
    
    async def process_chunk_with_semaphore(
        self, chunk: DocumentChunk, semaphore: asyncio.Semaphore
    ) -> List[DocumentChunk]:
        """
        一个带有限流器（Semaphore）的异步工作单元。

        Args:
            chunk: 待处理的块。
            preprocessor: 处理器实例。
            semaphore: 必须传入 asyncio.Semaphore 实例。

        Returns:
            成功时返回 [chunk]，失败时返回 []。
        """
        # async with semaphore: 会在执行前“请求”一个令牌。
        # 如果并发数已满，它会在这里异步等待，直到有令牌可用。
        async with semaphore:
            try:
                log.debug(f"开始处理块: {chunk.chunk_id}")

                return await self.preprocess(chunk)

            except asyncio.TimeoutError:
                log.error(f"处理块 {chunk.chunk_id} 超时。")
                return []
            except Exception as e:
                log.error(f"处理块 {chunk.chunk_id} 失败: {e}", exc_info=True)
                return []

    async def run_concurrent_preprocessing(
        self, chunks: List[DocumentChunk]
    ) -> List[DocumentChunk]:
        """
        在生产环境中并发处理所有文本块的主函数。

        Args:
            chunks: 所有待处理的块列表。

        Returns:
            成功处理和扩充的块的列表。
        """

        # 1. 创建信号量，限制并发数
        semaphore = asyncio.Semaphore(self.max_concurrency)

        log.info(f"开始并发处理 {len(chunks)} 个块 (最大并发数: {self.max_concurrency})...")

        # 2. 创建所有任务的列表
        tasks = []
        for chunk in chunks:
            tasks.append(self.process_chunk_with_semaphore(chunk, semaphore))

        # 3. 并发执行所有任务
        # results_list 是一个列表的列表, e.g., [[chunk1], [chunk2], [], [chunk4], ...]
        results_list = await asyncio.gather(*tasks)

        # 4. 展平 (Flatten) 结果，过滤掉失败的空列表
        enriched_chunks = [
            item
            for sublist in results_list
            if sublist  # 确保 sublist 不是空列表 []
            for item in sublist
        ]

        log.info(f"处理完成。成功扩充 {len(enriched_chunks)} / {len(chunks)} 个块。")
        return enriched_chunks