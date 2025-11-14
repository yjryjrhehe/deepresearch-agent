import logging

from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

from .vlm_enrichment_pipeline_options import VLMEnrichmentPipelineOptions
from .enrichment_models.formula_enrichment_model import FormulaVlmEnrichmentModel
from .enrichment_models.pic_enrichment_model import VLMPictureEnrichmentModel
from .enrichment_models.table_enrichment_model import LLMTableEnrichmentModel
from ...core.logging import setup_logging 

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)

class VlmEnrichmentPipeline(StandardPdfPipeline):
    """
    自定义 PDF 处理管道 (Pipeline)。
    
    此类继承自 StandardPdfPipeline，并注入了我们自定义的
    FormulaVlmEnrichmentModel。
    """
    def __init__(self, pipeline_options: VLMEnrichmentPipelineOptions):
        """
        初始化管道。

        Args:
            pipeline_options (VLMEnrichmentPipelineOptions): 我们的自定义选项。
        """
        super().__init__(pipeline_options)
        self.pipeline_options: VLMEnrichmentPipelineOptions = pipeline_options

        self.enrichment_pipe = [
            FormulaVlmEnrichmentModel(
                options=self.pipeline_options
            ),
            VLMPictureEnrichmentModel(
                options=self.pipeline_options
            ),
            LLMTableEnrichmentModel(
                options=self.pipeline_options
            ) 
        ]
        if self.pipeline_options.do_formula_vlm_recognition:
            # 告诉 docling 保持PDF渲染后端存活
            # 只有这样，BaseItemAndImageEnrichmentModel 才能接收到渲染的图像
            self.keep_backend = True
            log.info("FormulaVlmPipeline: 已启用 keep_backend 以支持公式图表渲染。")

    @classmethod
    def get_default_options(cls) -> VLMEnrichmentPipelineOptions:
        """
        告诉 docling 此管道使用我们的自定义选项类。
        """
        return VLMEnrichmentPipelineOptions()

