from docling.datamodel.pipeline_options import PdfPipelineOptions
from typing import Optional


class VLMEnrichmentPipelineOptions(PdfPipelineOptions):
    """
    自定义管道选项
    """
    # 是否启用 VLM 公式识别。
    do_formula_vlm_recognition: bool = True
    # 图片识别
    do_pic_enrichment: bool = True
    # 表格增强
    do_table_enrichment: bool = True

    # VLM 相关的配置项
    vlm_api_key: Optional[str] = None
    vlm_base_url: Optional[str] = None
    vlm_model: Optional[str] = None
    # VLM API 调用的最大并发线程数 
    vlm_max_concurrency: int = 5

    # VLM 相关的配置项
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    # llm API 调用的最大并发线程数 
    llm_max_concurrency: int = 5
    