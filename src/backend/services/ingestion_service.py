import logging
import asyncio
from typing import Callable, Awaitable, Optional

# --- 导入领域模型和接口 ---
from ..domain.interfaces import Ingestor, DocumentParser, PreProcessor, TextSplitter, SearchRepository
from ..domain.models import DocumentSource

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
        self.parser = parser
        self.splitter = splitter
        self.preprocessor = preprocessor
        self.store = store
        log.info("IngestionService 初始化完毕 (依赖已注入)。")

    async def _emit(self, msg: str, status_callback: Optional[Callable[[str], Awaitable[None]]] = None):
        """
        辅助方法：同时打印日志并调用回调 (如果提供了回调)
        """
        log.info(msg)
        if status_callback:
            await status_callback(msg)

    async def _emit_error(self, msg: str, status_callback: Optional[Callable[[str], Awaitable[None]]] = None):
        """
        错误辅助方法：打印错误日志并调用回调发送错误信息
        """
        log.error(msg)
        if status_callback:
            await status_callback(f"❌ {msg}")

    async def pipeline(
        self, 
        source: DocumentSource, 
        status_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ):
        """
        集成文档解析、分块、预处理和存入数据库的完整异步 pipeline。
        
        :param source: 文档源
        :param status_callback: [新增] 异步回调函数，用于向外部发送实时日志消息
        """
        
        await self._emit(f"--- [开始处理] 文档: {source.document_name} ---", status_callback)

        try:
            # --- 1. 解析 (Parse) ---
            await self._emit(f"步骤 1/4: 正在解析文档...", status_callback)

            md_content = await self.parser.parse(source)
            
            if not md_content or not str(md_content).strip():
                await self._emit_error(f"解析失败: 未提取到内容。", status_callback)
                return
            
            await self._emit(f"步骤 1/4: 解析成功，内容长度: {len(md_content)}", status_callback)

            # --- 2. 切分 (Split) ---
            await self._emit(f"步骤 2/4: 正在切分文本...", status_callback)
            # 假设 splitter.split 是同步的 CPU 密集型，使用 to_thread
            initial_chunks = await asyncio.to_thread(
                self.splitter.split, md_content, source
            )
            
            if not initial_chunks:
                await self._emit_error(f"切分失败或未产生任何块。", status_callback)
                return
                
            await self._emit(f"步骤 2/4: 切分成功，生成 {len(initial_chunks)} 个块。", status_callback)

            # --- 3. 预处理 (Preprocess) ---
            await self._emit(f"步骤 3/4: 正在进行智能预处理 (LLM)...", status_callback)
            enriched_chunks = await self.preprocessor.run_concurrent_preprocessing(initial_chunks)
            
            if not enriched_chunks:
                await self._emit_error(f"预处理失败: 未返回有效块。", status_callback)
                return
            
            await self._emit(f"步骤 3/4: 预处理成功，处理了 {len(enriched_chunks)} 个块。", status_callback)

            # --- 4. 存储 (Store) ---
            await self._emit(f"步骤 4/4: 正在写入向量数据库...", status_callback)
            await self.store.bulk_add_documents(enriched_chunks)
            
            await self._emit(f"步骤 4/4: 存储成功。", status_callback)
            await self._emit(f"✅ 文档 {source.document_name} 处理完毕！", status_callback)

        except FileNotFoundError as e:
            await self._emit_error(f"文件未找到: {source.file_path}", status_callback)
        except Exception as e:
            await self._emit_error(f"处理过程发生未知错误: {str(e)}", status_callback)
            import traceback
            traceback.print_exc()


