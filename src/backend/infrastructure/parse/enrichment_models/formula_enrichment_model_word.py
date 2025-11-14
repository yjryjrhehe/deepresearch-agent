import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

from openai import OpenAI
from docling_core.types.doc import (
    DoclingDocument,
    NodeItem,
    FormulaItem,
)
from docling.models.base_model import BaseEnrichmentModel

from ..vlm_enrichment_pipeline_options import VLMEnrichmentPipelineOptions
from ..prompt.llm_formula_enrichment_prompt import FORMULA_ENRICHMENT_PROMPT
from ....core.logging import setup_logging 

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)


class LLMFormulaEnrichmentModelWord(BaseEnrichmentModel):
    """
    针对 Word 文档的自定义公式增强模型 (基于 LLM)。

    此类继承自 BaseEnrichmentModel。它不接收图像（因为 .docx 后端
    不渲染公式），而是读取 FormulaItem.text 中可能存在的
    原始公式文本（例如 "a^2 + b^2 = c^2"）。

    然后，它调用一个纯文本 LLM (使用与 VLM 相同的 API) 
    来将其转换为标准 LaTeX 格式。
    """

    def __init__(self, options: VLMEnrichmentPipelineOptions):
        """
        初始化模型。

        Args:
            options (VLMEnrichmentPipelineOptions): 管道配置选项。
        """
        super().__init__()
        # 此模型是否启用，取决于 PDF 管道的同一个开关
        self.enabled = options.do_formula_vlm_recognition
        
        self.api_key = options.llm_api_key
        self.base_url = options.llm_base_url
        self.model = options.llm_model  

        self.max_concurrency = options.llm_max_concurrency
        log.info(f"LLMFormulaEnrichmentModelWord 已初始化，状态: {'启用' if self.enabled else '禁用'}")

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
            self.enabled
            and isinstance(element, FormulaItem)
        )

    def _ask_formula_llm_text(self, formula_text: str, prompt: str = FORMULA_ENRICHMENT_PROMPT) -> str:
        """
        调用 LLM (Text-to-Text) 识别公式文本并返回标准 LaTeX 格式。

        Args:
            formula_text (str): 从 FormulaItem.text 读出的原始文本。
            prompt (str): 指示 LLM 返回 LaTeX 的特定提示词。

        Returns:
            str: LLM 返回的 LaTeX 格式，或失败信息。
        """
        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            # 构建组合提示
            combined_prompt = (
                f"{prompt}\n\n"
                f"请将以下公式文本转换为 $$...$$ 格式的 LaTeX 标记："
                f"\n---\n{formula_text}\n---"
            )

            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": combined_prompt}]
            )
            recognized_text = completion.choices[0].message.content.strip()

            # --- LLM 输出后处理 ---
            # 尝试提取被 $$...$$ 包裹的内容
            match = re.search(r'\$\$(.*?)\$\$', recognized_text, re.DOTALL)
            if match:
                log.info(f"LLM 成功将文本 '{formula_text[:30]}...' 转换为 LaTeX。")
                return match.group(1) # 返回不带 $$ 的内容
            else:
                log.warning(f"LLM 输出未包含 $$...$$ ('{formula_text}')... 将按原样使用。")
                return recognized_text
                
        except Exception as e:
            log.warning(f"公式文本识别 LLM 失败 ({formula_text}): {e}")
            return "[公式识别失败]"

    def __call__(
        self,
        doc: DoclingDocument,
        element_batch: Iterable[NodeItem],
    ) -> Iterable[NodeItem]:
        """
        模型的核心处理逻辑 (Functor)。

        Args:
            doc (DoclingDocument): 当前文档对象。
            element_batch (Iterable[NodeItem]): 
                docling 管道传来的一批元素 (应为 FormulaItem)。

        Yields:
            NodeItem: 被 LLM 增强后的 *原始 FormulaItem* (已修改)。
        """
        if not self.enabled:
            # 如果被禁用，原样返回所有元素
            for item in element_batch:
                yield item
            return
        
        # 为当前批次创建线程池
        futures = {}
        with ThreadPoolExecutor(
            max_workers=self.max_concurrency, 
            thread_name_prefix="FormulaLLM_Word_Worker"
        ) as executor:
            
            # 1. 提交任务
            for element in element_batch:
                # 我们断言它一定是 FormulaItem，因为 is_processable 已经检查过
                assert isinstance(element, FormulaItem)
                
                # 获取原始公式文本
                original_text = element.text
                unique_id = id(element)

                if not original_text or original_text.isspace():
                    log.warning(f"FormulaItem (obj_id {unique_id}) 文本为空，跳过 LLM 转换。")
                    element.text = "[公式文本为空]"
                    yield element # 立即返回，不进线程池
                    continue
                
                # 1.2 提交 LLM 识别任务
                future = executor.submit(self._ask_formula_llm_text, original_text)
                futures[future] = element
        
        # 2. 收集结果
        for future in as_completed(futures):
            item = futures[future] # 获取原始的 item
            
            try:
                # 2.1 获取LLM结果 (LaTeX)
                latex_code = future.result()
                log.info(f"公式 (obj_id {id(item)}) LLM 转换成功。")
                
                # 打印验证
                print(f"***** (Word) LLM识别公式 ({latex_code}) 成功 *****")
                
                # 2.2 修改原始 item 的 text 属性
                item.text = latex_code

            except Exception as e:
                log.warning(f"公式 (obj_id {id(item)}) LLM 转换失败 (in-pipeline): {e}")
                item.text = "[公式识别失败]"

            # 无论成功失败，都必须 yield 回 item
            yield item