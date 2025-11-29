import logging
import asyncio
from typing import Callable, Awaitable, Optional, List

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
    
    Pipeline 的第 3 和 第 4 步合并为一个流式处理循环。
    不再一次性拿到所有 enriched_chunks，而是每处理完一批（BATCH_SIZE）就写入数据库。
    """

    # 定义写入数据库的批次大小，防止内存积压
    BATCH_SIZE = 50

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
        """辅助方法：同时打印日志并调用回调"""
        log.info(msg)
        if status_callback:
            await status_callback(msg)

    async def _emit_error(self, msg: str, status_callback: Optional[Callable[[str], Awaitable[None]]] = None):
        """错误辅助方法"""
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
            initial_chunks = await asyncio.to_thread(
                self.splitter.split, md_content, source
            )
            
            if not initial_chunks:
                await self._emit_error(f"切分失败或未产生任何块。", status_callback)
                return
                
            await self._emit(f"步骤 2/4: 切分成功，生成 {len(initial_chunks)} 个块。", status_callback)

            # --- 3 & 4. 预处理 (Preprocess) 并 流式写入 (Store) ---
            await self._emit(f"步骤 3-4: 正在并发预处理并分批写入 (Batch Size: {self.BATCH_SIZE})...", status_callback)
            
            processed_buffer: List[DocumentChunk] = []
            total_stored = 0
            
            # 使用 async for 消费 preprocessor 产生的流
            async for enriched_chunk in self.preprocessor.run_concurrent_preprocessing(initial_chunks):
                processed_buffer.append(enriched_chunk)
                
                # 如果缓冲区达到批次大小，执行写入
                if len(processed_buffer) >= self.BATCH_SIZE:
                    await self.store.bulk_add_documents(processed_buffer)
                    total_stored += len(processed_buffer)
                    await self._emit(f"  -> 已批次写入 {len(processed_buffer)} 个块 (累计: {total_stored})", status_callback)
                    processed_buffer.clear() # 清空缓冲区，释放内存

            # 循环结束后，处理剩余未满一批的块
            if processed_buffer:
                await self.store.bulk_add_documents(processed_buffer)
                total_stored += len(processed_buffer)
                await self._emit(f"  -> 写入剩余 {len(processed_buffer)} 个块", status_callback)
                processed_buffer.clear()

            if total_stored == 0:
                 await self._emit_error(f"警告: 流程结束但没有存储任何块 (可能是预处理全部失败)。", status_callback)
            else:
                await self._emit(f"步骤 3-4: 完成。共存储 {total_stored} 个块。", status_callback)
                await self._emit(f"✅ 文档 {source.document_name} 处理完毕！", status_callback)

        except FileNotFoundError:
            await self._emit_error(f"文件未找到: {source.file_path}", status_callback)
        except Exception as e:
            await self._emit_error(f"处理过程发生未知错误: {str(e)}", status_callback)
            import traceback
            traceback.print_exc()