import asyncio
import logging

from docling.document_converter import DocumentConverter

from ...domain.interfaces import DocumentParser
from ...domain.models import DocumentSource

log = logging.getLogger(__name__)

class DoclingParser(DocumentParser):
    def __init__(self, converter: DocumentConverter, max_concurrent_docs: int = 1):
        """
        初始化 DoclingParser。
        
        所有复杂的配置和实例化逻辑都已移至工厂方法中。
        此处仅接收已构建好的 converter 实例。

        :param converter: 已配置好 VLM Pipeline 的 DocumentConverter 实例
        :param max_concurrent_docs: 全局文档处理并发限制
        """
        log.info("DoclingParser 初始化 (依赖注入)...")
        self.doc_converter = converter
        # 设置信号量
        self.parse_semaphore = asyncio.Semaphore(max_concurrent_docs)
        log.info(f"DoclingParser 就绪。并发限制: {max_concurrent_docs}")

    async def parse(self, source: DocumentSource) -> str:
        """
        异步解析原始文档，使用 Semaphore 控制并发。
        """
        async with self.parse_semaphore:
            input_doc_path = source.file_path
            
            if not input_doc_path.exists():
                log.error(f"文件未找到: {input_doc_path}")
                raise FileNotFoundError(f"文件未找到: {input_doc_path}")
            
            try:
                # 内部阻塞函数
                def _blocking_convert_and_export():
                    # converter 已经是现成的了，直接调用
                    res = self.doc_converter.convert(input_doc_path)
                    md_content = res.document.export_to_markdown()
                    return md_content

                # 在线程池中运行阻塞的转换任务
                md_content = await asyncio.to_thread(_blocking_convert_and_export)
                
                log.info(f"转换完成: {source.file_path.name}")
                return md_content

            except Exception as e:
                log.error(f"解析文档时出错 {input_doc_path.name}: {e}", exc_info=True)
                raise