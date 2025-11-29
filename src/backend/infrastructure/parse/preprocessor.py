import logging
from typing import List, AsyncGenerator
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
    
    修改说明：
    已将处理逻辑改为流式（Generator）模式，结合 IngestionService 的分批写入，
    能够有效降低内存占用。
    """

    def __init__(self, llm: BaseChatModel, max_concurrency: int = 5):
        """
        初始化LLM预处理器。
        
        :param llm: 注入的 LLM 客户端实例 (依赖注入)
        :param max_concurrency: 最大并发数
        """
        self.llm = llm
        self.max_concurrency = max_concurrency
        
        log.info("LLMPreprocessor 初始化完成 (依赖已注入)。")

    async def preprocess(self, chunk: DocumentChunk) -> List[DocumentChunk]:
        """
        处理单个 DocumentChunk 对象，为其生成摘要和假设性问题。
        """
        try:
            # 1. 准备父标题字符串
            parent_title_str = " > ".join(chunk.parent_headings)

            # 2. 准备llm的输入
            prompt = LLM_PREPROCESS_PROMPT.format(
                parent_title=parent_title_str, doc=chunk.content
            )

            # 3. 调用LLM链
            result = await self.llm.ainvoke(prompt)
            result = json_repair.loads(result.content)

            # 4. 扩充（Enrich）原始的 DocumentChunk 对象
            chunk.summary = result.get("summary")
            chunk.hypothetical_questions = result.get("questions", [])

            log.debug(f"成功处理块 {chunk.chunk_id} (文档: {chunk.document_name})")

            return [chunk]

        except Exception as e:
            log.error(
                f"处理块 {chunk.chunk_id} (文档: {chunk.document_name}) 时失败: {e}"
            )
            return []
    
    async def process_chunk_with_semaphore(
        self, chunk: DocumentChunk, semaphore: asyncio.Semaphore
    ) -> List[DocumentChunk]:
        """
        一个带有限流器（Semaphore）的异步工作单元。
        """
        async with semaphore:
            try:
                # log.debug(f"开始处理块: {chunk.chunk_id}")
                return await self.preprocess(chunk)

            except asyncio.TimeoutError:
                log.error(f"处理块 {chunk.chunk_id} 超时。")
                return []
            except Exception as e:
                log.error(f"处理块 {chunk.chunk_id} 失败: {e}", exc_info=True)
                return []

    async def run_concurrent_preprocessing(
        self, chunks: List[DocumentChunk]
    ) -> AsyncGenerator[DocumentChunk, None]:
        """
        在生产环境中并发处理所有文本块，并以流的方式产出结果。

        修改点：
        不再使用 asyncio.gather 等待所有任务完成，而是使用 asyncio.as_completed。
        这允许只要有一个块处理完，就立即 yield 返回给调用者，
        从而允许调用者（IngestionService）进行分批写入，释放内存。

        Args:
            chunks: 所有待处理的块列表。

        Yields:
            DocumentChunk: 处理完成的一个块。
        """

        # 1. 创建信号量，限制并发数
        semaphore = asyncio.Semaphore(self.max_concurrency)

        log.info(f"开始并发处理 {len(chunks)} 个块 (最大并发数: {self.max_concurrency})...")

        # 2. 创建任务列表
        # 注意：这里创建了 Task 对象，但并没有等待它们。
        # Semaphore 会控制真正运行 LLM 请求的并发量。
        tasks = [
            self.process_chunk_with_semaphore(chunk, semaphore) 
            for chunk in chunks
        ]

        # 3. 使用 as_completed 实现流式处理
        # 只要有任务完成，循环就会继续，而不需要等待所有任务结束
        processed_count = 0
        
        for future in asyncio.as_completed(tasks):
            try:
                # 获取单个任务的结果（结果是一个 list，通常包含 1 个 chunk 或 0 个）
                results = await future
                
                for chunk in results:
                    processed_count += 1
                    yield chunk
                    
            except Exception as e:
                # 防御性编程：虽然 process_chunk_with_semaphore 内部捕获了异常，
                # 但防止 future 获取结果时本身的异常打断整个流
                log.error(f"获取并发任务结果时发生未捕获异常: {e}")

        log.info(f"并发处理流结束。累计成功产出 {processed_count} 个块。")