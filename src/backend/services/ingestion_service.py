import logging
import asyncio
from typing import List

# --- 导入领域模型和接口 ---
from ..domain.interfaces import Ingestor, DocumentParser, PreProcessor, TextSplitter, SearchRepository
from ..domain.models import DocumentSource, DocumentChunk

# --- 导入日志配置 ---
from ..core.logging import setup_logging

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)


class IngestionService(Ingestor):
    """
    文档摄入服务 (业务流程编排)。
    实现了 Ingestor 接口。
    
    职责: 编排完整的文档摄入流程（流程图1）。
    1. 调用 DocumentParser (解析)
    2. 调用 TextSplitter (切分)
    3. 循环/并发调用 PreProcessor (预处理，生成摘要等)
    4. 调用 SearchRepository.bulk_add_documents (存入)
    """

    def __init__(
        self,
        parser: DocumentParser,
        splitter: TextSplitter,
        preprocessor: PreProcessor,
        store: SearchRepository
    ):
        """
        初始化摄入服务。
        """
        self.parser = parser
        self.splitter = splitter
        self.preprocessor = preprocessor
        self.store = store

        log.info("IngestionService 初始化完毕 (依赖已注入)。")

    async def pipeline(self, source: DocumentSource):
        """
        集成文档解析、分块、预处理和存入数据库的完整异步 pipeline。
        
        :param source: 包含待处理文档路径的 DocumentSource 对象。
        """
        log.info(f"--- [PIPELINE START] ---")
        log.info(f"开始处理文档: {source.document_name} (ID: {source.document_id})")

        try:
            # --- 1. 解析 (Parse) ---
            # self.parser.parse() 是一个异步 I/O 密集型操作 (来自 DoclingParser)
            # 我们使用 asyncio.to_thread 将其移出主事件循环，防止阻塞。
            log.info(f"步骤 1/4: [解析] 正在使用 DoclingParser 解析...")
            md_content = await self.parser.parse(source)
            
            if not md_content or not md_content.strip():
                log.error(f"[PIPELINE FAILED] 解析失败: {source.document_name} (ID: {source.document_id}) 未返回任何内容。")
                return
            
            log.info(f"步骤 1/4: [解析] 成功，Markdown 内容长度: {len(md_content)}")

            # --- 2. 切分 (Split) ---
            # self.splitter.split() 是一个同步 CPU 密集型操作 (来自 MarkdownSplitter)
            # 同样使用 asyncio.to_thread。
            log.info(f"步骤 2/4: [切分] 正在使用 MarkdownSplitter 切分...")
            initial_chunks: List[DocumentChunk] = await asyncio.to_thread(
                self.splitter.split, md_content, source
            )
            
            if not initial_chunks:
                log.warning(f"[PIPELINE 终止] 切分失败或未产生任何块: {source.document_name}")
                return
                
            log.info(f"步骤 2/4: [切分] 成功，切分为 {len(initial_chunks)} 个初始块。")

            # --- 3. 预处理 (Preprocess) ---
            # self.preprocessor.run_concurrent_preprocessing() 是一个异步操作 (来自 LLMPreprocessor)
            # 它内部处理了并发和LLM调用。
            log.info(f"步骤 3/4: [预处理] 正在使用 LLMPreprocessor 并发处理 {len(initial_chunks)} 个块...")
            enriched_chunks = await self.preprocessor.run_concurrent_preprocessing(initial_chunks)
            
            if not enriched_chunks:
                log.error(f"[PIPELINE FAILED] 预处理失败: {source.document_name} (ID: {source.document_id}) 未返回任何有效块。")
                return
            
            log.info(f"步骤 3/4: [预处理] 成功，{len(enriched_chunks)} / {len(initial_chunks)} 个块已扩充。")

            # --- 4. 存储 (Store) ---
            # self.store.bulk_add_documents() 是一个异步操作 (来自 AsyncOpenSearchRAGStore)
            log.info(f"步骤 4/4: [存储] 正在使用 AsyncOpenSearchRAGStore 批量存入 {len(enriched_chunks)} 个块...")
            await self.store.bulk_add_documents(enriched_chunks)
            
            log.info(f"步骤 4/4: [存储] 成功。")
            log.info(f"--- [PIPELINE SUCCESS] ---")
            log.info(f"文档 {source.document_name} (ID: {source.document_id}) 处理完毕。")

        except FileNotFoundError as e:
            log.error(f"[PIPELINE FAILED] 文件未找到: {source.file_path}. 错误: {e}", exc_info=True)
        except Exception as e:
            log.error(f"[PIPELINE FAILED] 处理 {source.document_name} 时发生未知错误: {e}", exc_info=True)