import logging

# 导入 DOCX 的标准管道 SimplePipeline
from docling.pipeline.simple_pipeline import SimplePipeline
from .vlm_enrichment_pipeline_options import VLMEnrichmentPipelineOptions

# --- 导入模型 ---
from .enrichment_models.pic_enrichment_model import VLMPictureEnrichmentModel
from .enrichment_models.formula_enrichment_model_word import LLMFormulaEnrichmentModelWord
from ...core.logging import setup_logging 

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)

class VlmEnrichmentWordPipeline(SimplePipeline):
    """
    自定义 Word（.docx）处理管道 (Pipeline)。
    
    此类继承自 SimplePipeline (DOCX 的默认管道)，
    并注入了用于处理 *图片* 和 *公式* 的增强模型。
    """
    
    def __init__(self, pipeline_options: VLMEnrichmentPipelineOptions):
        """
        初始化管道。

        Args:
            pipeline_options (VLMEnrichmentPipelineOptions): 我们的自定义选项。
        """
        super().__init__(pipeline_options)
        
        # 2. 明确覆盖 enrichment_pipe
        #    同时加载图片模型和公式模型
        self.enrichment_pipe = [
            VLMPictureEnrichmentModel(
                options=self.pipeline_options
            ),
            LLMFormulaEnrichmentModelWord(
                options=self.pipeline_options
            )
        ]
        
        log.info("VlmEnrichmentWordPipeline 已初始化，已注入 [图片VLM] 和 [公式LLM] 模型。")

    @classmethod
    def get_default_options(cls) -> VLMEnrichmentPipelineOptions:
        """
        告诉 docling 此管道使用自定义选项类。
        """
        return VLMEnrichmentPipelineOptions()