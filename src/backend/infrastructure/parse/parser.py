from pathlib import Path
import logging
import time

from docling.document_converter import InputFormat, DocumentConverter, PdfFormatOption, WordFormatOption
from docling.datamodel.pipeline_options import AcceleratorDevice, AcceleratorOptions

from ...domain.interfaces import DocumentParser
from ...domain.models import DocumentSource

# --- VLM 管道导入 ---
from .vlm_enrichment_pipeline_options import VLMEnrichmentPipelineOptions
from .vlm_enrichment_pipeline import VlmEnrichmentPipeline
from .vlm_enrichment_pipeline_word import VlmEnrichmentWordPipeline
from ...core.logging import setup_logging 

from ...core.config import settings

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)

class DoclingParser(DocumentParser):
    def __init__(self):
        """
        初始化时，一次性配置 DocumentConverter。
        """
        log.info("初始化 DoclingVLMParser...")
        try:
            self.doc_converter = self._setup_converter()
            log.info("DoclingVLMParser 初始化完成。")
        except Exception as e:
            log.error(f"DoclingVLMParser 初始化失败: {e}", exc_info=True)
            raise
    
    def _setup_converter(self) -> DocumentConverter:
        """
        私有方法：从 settings 构建 VLM 管道和 DocumentConverter。
        """
        
        # --- 1. 配置 VLMEnrichmentPipelineOptions ---
        pipeline_options = VLMEnrichmentPipelineOptions()
        
        # Docling 基础配置 (从 settings 加载)
        pipeline_options.images_scale = settings.DOCLING_IMAGES_SCALE
        pipeline_options.generate_picture_images = True # 必须为 True，VLM 才能获取图片
        
        # 自定义增强配置 (从 settings 加载)
        pipeline_options.do_formula_vlm_recognition = settings.DOCLING_DO_FORMULA_RECOGNITION
        pipeline_options.do_table_enrichment = settings.DOCLING_DO_TABLE_ENRICHMENT
        pipeline_options.do_pic_enrichment = settings.DOCLING_DO_PIC_ENRICHMENT
        
        # 加速器配置 (从 settings 加载)
        try:
            device = AcceleratorDevice[settings.DOCLING_ACCELERATOR_DEVICE.upper()]
        except KeyError:
            log.warning(f"无效的 DOCLING_ACCELERATOR_DEVICE: '{settings.DOCLING_ACCELERATOR_DEVICE}'. 回退到 CPU。")
            device = AcceleratorDevice.CPU

        pipeline_options.accelerator_options = AcceleratorOptions(
            device=device,
            num_threads=settings.DOCLING_ACCELERATOR_NUM_THREADS
        )
        pipeline_options.do_ocr = settings.DOCLING_DO_OCR

        # 注入 VLM 配置 (从 settings 加载)
        pipeline_options.vlm_api_key = settings.DOCLING_VLM_API_KEY
        pipeline_options.vlm_base_url = settings.DOCLING_VLM_BASE_URL
        pipeline_options.vlm_model = settings.DOCLING_VLM_MODEL
        pipeline_options.vlm_max_concurrency = settings.DOCLING_VLM_MAX_CONCURRENCY
        
        # 注入 llm 配置 (从 settings 加载)
        pipeline_options.llm_api_key = settings.DOCLING_LLM_API_KEY
        pipeline_options.llm_base_url = settings.DOCLING_LLM_BASE_URL
        pipeline_options.llm_model = settings.DOCLING_LLM_MODEL
        pipeline_options.llm_max_concurrency = settings.DOCLING_LLM_MAX_CONCURRENCY

        # --- 2. 配置 DocumentConverter ---
        log.info("配置 DocumentConverter...")
        doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=VlmEnrichmentPipeline,  
                    pipeline_options=pipeline_options,
                ),
                InputFormat.DOCX: WordFormatOption(
                    pipeline_cls=VlmEnrichmentWordPipeline,  
                    pipeline_options=pipeline_options,
                ),
            }
        )
        return doc_converter

    def parse(self, source: DocumentSource) -> str:
        """
        解析原始文档，并返回 Markdown 字符串。
        
        :param source: DocumentSource 对象，必须包含 file_path。
        :return: Markdown 格式的字符串。
        """
        input_doc_path = source.file_path
        
        if not input_doc_path.exists():
            log.error(f"文件未找到: {input_doc_path}")
            raise FileNotFoundError(f"文件未找到: {input_doc_path}")
        
        log.info(f"开始转换 (DoclingParser): {input_doc_path.name}")

        try:
            # --- 1. 执行转换 ---
            res = self.doc_converter.convert(input_doc_path)
            
            # --- 2. 导出为md文档 ---
            md_content = res.document.export_to_markdown()
            
            return md_content

        except Exception as e:
            log.error(f"解析文档时出错 {input_doc_path.name}: {e}", exc_info=True)
            raise # 重新抛出异常，以便上层服务捕获

# ==================================
#    测试模块 (if __name__ == "__main__")
# ==================================
if __name__ == "__main__":
    
    log.info("--- 开始 DoclingVLMParser 测试 ---")
    log.warning("确保 .env 文件已在正确位置并包含所有 DOCLING_... 变量。")
    start = time.time()
    
    # 1. 初始化解析器
    # (这将从 .env 加载配置)
    try:
        parser = DoclingParser()
    except Exception as e:
        log.error(f"无法初始化 DoclingVLMParser (请检查 .env 文件和配置): {e}", exc_info=True)
        exit(1)

    # 2. 定义输入和输出
    # input_doc_path: Path = Path(r".\test\test.pdf")
    input_doc_path: Path = Path(r"E:\02open-project\deepresearch-agent\test\parser_test\test.pdf")
    output_md_path: Path = Path(r"E:\02open-project\deepresearch-agent\test\parser_test\test.md")
    
    # 3. 创建 DocumentSource
    doc_source = DocumentSource(file_path=input_doc_path)
    
    # 4. 执行解析 (调用 parse)
    try:
        log.info(f"开始解析 {doc_source.file_path}...")
        md_string = parser.parse(doc_source)
        
        # 5. 将返回的字符串保存到文件
        with open(output_md_path, 'w', encoding='utf-8') as f:
            f.write(md_string)
            
        log.info(f"成功！Markdown 内容已保存到: {output_md_path}")
        
    except FileNotFoundError:
        log.error(f"测试失败: 输入文件 {input_doc_path} 未找到。")
    except Exception as e:
        log.error(f"测试期间发生错误: {e}", exc_info=True)

    end = time.time()
    log.info(f"总转换时间为：{end-start:.6f} 秒。")