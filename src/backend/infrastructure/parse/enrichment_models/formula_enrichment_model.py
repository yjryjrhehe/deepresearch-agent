import logging
import base64
import re
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

from PIL import Image
from openai import OpenAI

# --- Docling 核心导入 ---
from docling_core.types.doc import (
    FormulaItem, 
    DoclingDocument, 
    NodeItem,
)
from docling.datamodel.base_models import ItemAndImageEnrichmentElement
from docling.models.base_model import BaseItemAndImageEnrichmentModel
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

from ..prompt.formula_recognition_prompt import FORMULA_RECOGNITION_PROMPT
from ..vlm_enrichment_pipeline_options import VLMEnrichmentPipelineOptions
from ....core.logging import setup_logging 

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)

class FormulaVlmEnrichmentModel(BaseItemAndImageEnrichmentModel):
    """
    自定义公式增强模型 (Enrichment Model)。
    
    此类继承自 BaseItemAndImageEnrichmentModel，使其能够在 docling 管道
    处理过程中同时访问到文档元素 (item) 及其渲染的图像 (image)。
    这是实现【边解析边识别】的关键。
    """
    images_scale: float = 2.6 

    def __init__(self, options:VLMEnrichmentPipelineOptions):
        """
        初始化模型。

        Args:
            options:VLMEnrichmentPipelineOptions
        """
        self.enabled = options.do_formula_vlm_recognition
        self.api_key = options.vlm_api_key
        self.base_url = options.vlm_base_url
        self.model = options.vlm_model

        self.max_concurrency = options.vlm_max_concurrency
        log.info(f"FormulaVlmEnrichmentModel 已初始化，状态: {'启用' if self.enabled else '禁用'}")

    def is_processable(self, doc: DoclingDocument, element: NodeItem) -> bool:
        """
        定义此模型应处理哪些元素。

        Args:
            doc (DoclingDocument): 当前文档对象。
            element (NodeItem): 待检查的元素。

        Returns:
            bool: 如果是 FormulaItem 且模型已启用，返回 True。
        """
        return (
            self.enabled                          # 1. 仅当开关启用
            and isinstance(element, FormulaItem)  # 2. 且元素是 FormulaItem 时
        )
    
    def _ask_formula_vlm_base64(self, pil_image: Image.Image, prompt: str = FORMULA_RECOGNITION_PROMPT) -> str:
        """
        调用 VLM 识别公式图像，并返回标准 LaTeX 格式。

        Args:
            pil_image (Image.Image): 公式的高清 PIL 图像。
            prompt (str): 指示 VLM 返回 LaTeX 的特定提示词。

        Returns:
            str: VLM 返回的 $$...$$ 格式的 LaTeX，或失败信息。
        """
        try:
            buffered = BytesIO()
            # 公式必须使用 PNG 格式，保留最佳清晰度，避免 JPEG 压缩失真
            pil_image.save(buffered, format="PNG") 
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
            ]
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}]
            )
            recognized_text = completion.choices[0].message.content.strip()

            # --- VLM 输出后处理 ---
            match = re.search(r'\$\$(.*?)\$\$', recognized_text, re.DOTALL)
            if match:
                log.warning(f"VLM 返回了额外文本，已提取 LaTeX。")
                return match.group(1)
            else:
                log.warning(f"VLM 输出未包含 LaTeX，请检查是否正确。")
                return recognized_text
        except Exception as e:
            log.warning(f"公式识别 VLM 失败: {e}")
            return "[公式识别失败]"

    def __call__(
        self,
        doc: DoclingDocument,
        element_batch: Iterable[ItemAndImageEnrichmentElement],
    ) -> Iterable[NodeItem]:
        """
        模型的核心处理逻辑 (Functor)。
        
        此方法将接收 FormulaItem，但会返回（yield）一个
        *新的 TextItem* 来替换它。这个新的 TextItem 会包含
        VLM 识别的 LaTeX、原始位置信息 (prov) 和元数据 (metadata)。

        Args:
            doc (DoclingDocument): 当前文档对象。
            element_batch (Iterable[ItemAndImageEnrichmentElement]):
                docling 管道传来的一批元素，每个元素都包含 .item 和 .image。

        Yields:
            NodeItem: 被 VLM 增强后的 *新 TextItem*。
        """
        if not self.enabled:
            # 如果被禁用，原样返回所有元素，不做任何处理
            for el in element_batch:
                yield el.item
            return
        
        # 为当前批次创建线程池
        futures = {}
        with ThreadPoolExecutor(max_workers=self.max_concurrency, thread_name_prefix="FormulaVLM_Worker") as executor:
            
            # 1. 提交任务
            for enrich_element in element_batch:
                formula_image: Image.Image = enrich_element.image # 这就是 PIL 图像
                item: FormulaItem = enrich_element.item           # 这就是 FormulaItem
                
                # 使用 Python 内置的 id() 函数获取唯一标识
                unique_id = id(item) 

                if formula_image is None:
                    log.warning(f"EnrichmentModel 收到 None 图像 (obj_id {unique_id}). 跳过。")
                    # 即使失败，也必须 yield *原始* item，否则它会丢失
                    futures[None] = (item, None, unique_id) # 用 None 作为 future 键
                    continue

                # 1.2 提交 VLM 识别任务
                future = executor.submit(self._ask_formula_vlm_base64, formula_image)
                # 存储 future 与 (item, 图像路径, 唯一ID) 的映射
                futures[future] = (item, unique_id)
        
        # --- FIX: 处理 None-future 键 (图像加载失败的) ---
        if None in futures:
            item, unique_id = futures[None]
            log.warning(f"公式 (obj_id {unique_id}) 因图像加载失败，将替换为失败的TextItem。")
            item.text = '[公式图像加载失败]'

            yield item
            del futures[None] # 从字典中移除

        # 2. 收集结果
        for future in as_completed(futures):
            item, unique_id = futures[future]
            
            try:
                # 2.1 获取VLM结果 (LaTeX)
                latex_code = future.result()
                log.info(f"公式 (obj_id {unique_id}) VLM 识别成功。")
                # 打印验证是否识别成功公式
                print(f"***** VLM识别公式 ({latex_code})成功 *****") 
            except Exception as e:
                log.warning(f"公式 (obj_id {unique_id}) VLM 识别失败 (in-pipeline): {e}")
                latex_code = "[公式识别失败]"

            item.text = latex_code

            yield item


    