import logging
from functools import lru_cache

from docling.document_converter import (
    InputFormat, 
    DocumentConverter, 
    PdfFormatOption, 
    WordFormatOption
)
from docling.datamodel.pipeline_options import AcceleratorDevice, AcceleratorOptions

from .preprocessor import LLMPreprocessor
# 导入其他工厂函数
from ..llm.factory import get_preprocessing_llm 
from .parser import DoclingParser
from .vlm_enrichment_pipeline_options import VLMEnrichmentPipelineOptions
from .vlm_enrichment_pipeline import VlmEnrichmentPipeline
from .vlm_enrichment_pipeline_word import VlmEnrichmentWordPipeline

from .splitter import MarkdownSplitter

# 导入配置
from ...core.config import settings

log = logging.getLogger(__name__)

@lru_cache()
def get_docling_parser() -> DoclingParser:
    """
    [工厂方法] 获取 DoclingParser 单例。
    
    负责：
    1. 读取 settings 配置。
    2. 配置 VLM Pipeline Options。
    3. 初始化 DocumentConverter。
    4. 返回注入好依赖的 DoclingParser。
    """
    log.info("开始构建 DoclingParser...")

    try:
        # --- 1. 配置 VLMEnrichmentPipelineOptions ---
        pipeline_options = VLMEnrichmentPipelineOptions()
        
        # 基础配置 (使用 settings.docling_general)
        pipeline_options.images_scale = settings.docling_general.images_scale
        pipeline_options.generate_picture_images = True 
        
        # 增强功能开关 (使用 settings.docling_general)
        pipeline_options.do_formula_vlm_recognition = settings.docling_general.do_formula_recognition
        pipeline_options.do_table_enrichment = settings.docling_general.do_table_enrichment
        pipeline_options.do_pic_enrichment = settings.docling_general.do_pic_enrichment
        pipeline_options.do_ocr = settings.docling_general.do_ocr
        
        # 加速器配置 (使用 settings.docling_general)
        try:
            device_str = settings.docling_general.accelerator_device.upper()
            device = AcceleratorDevice[device_str]
        except KeyError:
            log.warning(f"无效的加速器配置 '{settings.docling_general.accelerator_device}'，回退到 CPU。")
            device = AcceleratorDevice.CPU

        pipeline_options.accelerator_options = AcceleratorOptions(
            device=device,
            num_threads=settings.docling_general.accelerator_num_threads
        )

        # 注入 VLM / LLM API 配置 (使用 settings.docling_vlm 和 settings.docling_llm)
        pipeline_options.vlm_api_key = settings.docling_vlm.api_key
        pipeline_options.vlm_base_url = settings.docling_vlm.base_url
        pipeline_options.vlm_model = settings.docling_vlm.model
        pipeline_options.vlm_max_concurrency = settings.docling_vlm.max_concurrency
        
        pipeline_options.llm_api_key = settings.docling_llm.api_key
        pipeline_options.llm_base_url = settings.docling_llm.base_url
        pipeline_options.llm_model = settings.docling_llm.model
        pipeline_options.llm_max_concurrency = settings.docling_llm.max_concurrency

        # --- 2. 配置 DocumentConverter ---
        log.debug("配置 DocumentConverter...")
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
        
        # --- 3. 实例化 Parser ---
        MAX_CONCURRENT_DOCS = 1 
        
        return DoclingParser(
            converter=doc_converter, 
            max_concurrent_docs=MAX_CONCURRENT_DOCS
        )

    except Exception as e:
        log.error(f"构建 DoclingParser 失败: {e}", exc_info=True)
        raise e

@lru_cache()
def get_llm_preprocessor() -> LLMPreprocessor:
    """
    [工厂方法] 获取 LLMPreprocessor 单例。
    
    负责：
    1. 获取底层的 LLM Client。
    2. 读取配置 (并发数)。
    3. 实例化并注入依赖。
    """
    # 1. 获取依赖
    llm_client = get_preprocessing_llm()
    
    # 2. 组装并返回 (使用 settings.preprocessing_llm)
    return LLMPreprocessor(
        llm=llm_client,
        max_concurrency=settings.preprocessing_llm.max_concurrency
    )

@lru_cache()
def get_markdown_splitter() -> MarkdownSplitter:
    """
    [工厂方法] 获取 MarkdownSplitter 单例。
    
    负责从 settings 读取分块策略配置，并注入到 Splitter 实例中。
    (使用 settings.splitter)
    """
    return MarkdownSplitter(
        headers_to_split_on=settings.splitter.headers_to_split_on,
        max_chunk_tokens=settings.splitter.max_chunk_tokens,
        chunk_overlap_tokens=settings.splitter.chunk_overlap_tokens,
        encoding_name=settings.splitter.encoding_name
    )
