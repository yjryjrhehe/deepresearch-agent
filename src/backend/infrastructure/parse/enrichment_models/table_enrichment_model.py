import logging
import base64
import concurrent.futures
from io import BytesIO
from collections.abc import Iterable
from typing import Any, Literal

# --- Pydantic 和 PIL ---
from pydantic import Field
from PIL import Image

# --- OpenAI VLM 相关 ---
from openai import OpenAI

# --- Docling 核心导入 ---
from docling_core.types.doc import (
    DoclingDocument,
    NodeItem,
    TableItem,
    BaseAnnotation
)
from docling.models.base_model import BaseEnrichmentModel

from ..prompt.table_repair_prompt import TABLE_REPAIR_PROMPT
from ..vlm_enrichment_pipeline_options import VLMEnrichmentPipelineOptions
from ....core.logging import setup_logging 

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)

class LLMTableEnrichmentData(BaseAnnotation):
    """
    用于存储 VLM 表格增强结果的自定义标注。
    """
    kind: Literal["llm_table_enrichment"] = "llm_table_enrichment"

    provenance: str = "llm_table_enricher-0.0.1"
    llm_markdown_table: str = Field(..., description="由 VLM 生成或从 DataFrame 转换的 Markdown 表格")
    status: str = Field(..., description="处理状态 (e.g., 'success_vlm', 'success_dataframe', 'failed')")


class LLMTableEnrichmentModel(BaseEnrichmentModel):
    """
    实现表格增强的核心逻辑。
    (已更新以使用新的 PipelineOptions 结构)
    """

    def __init__(self, options: VLMEnrichmentPipelineOptions):
        """
        初始化模型，从 options 中获取配置。

        Args:
            options (VLMEnrichmentPipelineOptions): 包含所有配置的对象。
        """
        
        # 1. 从新选项 'do_table_enrichment' 读取"启用"状态
        self.enabled = options.do_table_enrichment
        
        # 2. 存储 VLM 配置 (使用新选项名称)
        self.api_key = options.vlm_api_key
        self.base_url = options.vlm_base_url
        self.model = options.vlm_model
        self.prompt = TABLE_REPAIR_PROMPT
        
        # 3. 存储线程池最大工作数 (使用新选项 'vlm_max_concurrency')
        # self.max_workers 是 ThreadPoolExecutor 将要读取的字段
        self.max_workers = options.vlm_max_concurrency

        # 4. **重要**：添加启动时配置校验
        # 如果 VLM 增强被启用，则 API 密钥、URL 和模型必须已提供
        if self.enabled:
            if not self.api_key:
                log.error("VLM 增强 (do_table_enrichment) 已启用, 但 'vlm_api_key' 未在 PipelineOptions 中设置。")
                raise ValueError("LLMTableEnrichmentModel 必须在启用时提供 'vlm_api_key'")
            
            if not self.base_url:
                log.error("VLM 增强 (do_table_enrichment) 已启用, 但 'vlm_base_url' 未在 PipelineOptions 中设置。")
                raise ValueError("LLMTableEnrichmentModel 必须在启用时提供 'vlm_base_url'")

            if not self.model:
                log.error("VLM 增强 (do_table_enrichment) 已启用, 但 'vlm_model' 未在 PipelineOptions 中设置。")
                raise ValueError("LLMTableEnrichmentModel 必须在启用时提供 'vlm_model'")
        
        log.info(f"LLMTableEnrichmentModel 初始化, VLM 增强: {'启用' if self.enabled else '禁用'}")
        if self.enabled:
            log.info(f"  -> VLM 模型: {self.model}")
            log.info(f"  -> VLM 并发数: {self.max_workers}")


    def is_processable(self, doc: DoclingDocument, element: NodeItem) -> bool:
        """
        检查此模型是否应该处理给定的文档元素。
        """
        # 我们只关心 TableItem
        return self.enabled and isinstance(element, TableItem)

    # --- 移植的 VLM 辅助函数 (保持不变) ---
    
    def _ask_table_vlm(self, pil_image: Image.Image, prompt: str) -> str:
        """
        调用 VLM (多模态大模型) 修复或识别表格图像。
        """
        try:
            buffered = BytesIO()
            pil_image.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
            ]
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}]
            )
            return completion.choices[0].message.content.strip()
        
        except Exception as e:
            log.warning(f"表格图像修复 VLM 失败: {e}")
            return f"[表格修复失败: {e}]"

    @staticmethod
    def _split_table_image_rows(pil_img: Image.Image, row_height: int = 400) -> list:
        width, height = pil_img.size
        slices = []
        for top in range(0, height, row_height):
            bottom = min(top + row_height, height)
            crop = pil_img.crop((0, top, width, bottom))
            slices.append(crop)
        return slices

    @staticmethod
    def _merge_small_chunks(chunks: list, min_height: int = 300, min_width: int = 20) -> list:
        merged_chunks = []
        temp_chunk = None

        for chunk in chunks:
            width, height = chunk.size
            if height < min_height or width < min_width:
                if temp_chunk is None:
                    temp_chunk = chunk
                else:
                    new_chunk = Image.new("RGB", (max(temp_chunk.width, chunk.width), temp_chunk.height + chunk.height))
                    new_chunk.paste(temp_chunk, (0, 0))
                    new_chunk.paste(chunk, (0, temp_chunk.height))
                    temp_chunk = new_chunk
            else:
                if temp_chunk is not None:
                    merged_chunks.append(temp_chunk)
                    temp_chunk = None
                merged_chunks.append(chunk)

        if temp_chunk is not None:
            if temp_chunk.height < min_height or temp_chunk.width < min_width:
                 new_height = max(temp_chunk.height, min_height)
                 new_width = max(temp_chunk.width, min_width)
                 new_chunk = Image.new("RGB", (new_width, new_height), (255, 255, 255))
                 new_chunk.paste(temp_chunk, (0, 0))
                 merged_chunks.append(new_chunk)
            else:
                merged_chunks.append(temp_chunk)
                
        return merged_chunks

    # --- 核心处理逻辑 ---

    def _process_table(self, doc: DoclingDocument, element: TableItem) -> TableItem:
        """
        处理单个 TableItem 的函数。
        此函数将在线程池中被调用。
        """
        try:
            pil_img = element.get_image(doc)
            
            try:
                table_df = element.export_to_dataframe()
                is_abnormal = not table_df.columns.is_unique or table_df.shape[1] < 2
            except Exception as df_error:
                log.warning(f"无法导出 {element.self_ref} 为 DataFrame ({df_error})，将使用 VLM。")
                is_abnormal = True
                table_df = None 

            if is_abnormal:
                log.info(f"表格 {element.self_ref} 结构异常，使用 VLM 修复...")
                
                sub_images = self._split_table_image_rows(pil_img)
                sub_images = self._merge_small_chunks(sub_images)
                
                full_md_lines = []
                
                for idx, chunk_img in enumerate(sub_images):
                    # 调用 _ask_table_vlm, 它会使用 self.prompt
                    chunk_md = self._ask_table_vlm(chunk_img, self.prompt)
                    
                    if "[表格修复失败" in chunk_md:
                        log.warning(f"表格 {element.self_ref} 的切片 {idx} 修复失败。")
                        continue

                    lines = chunk_md.splitlines()
                    
                    if lines and lines[0].strip() == "```markdown":
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]

                    if idx == 0:
                        full_md_lines.extend(lines)
                    else:
                        full_md_lines.extend(lines[2:])
                
                markdown_result = "\n".join(full_md_lines)
                status = "success_vlm"

            else:
                log.info(f"表格 {element.self_ref} 结构正常，使用 DataFrame 转换。")
                markdown_result = table_df.to_markdown(index=False)
                status = "success_dataframe"

        except Exception as e:
            log.error(f"处理表格 {element.self_ref} 时发生严重错误: {e}", exc_info=True)
            markdown_result = f"[表格处理失败: {e}]"
            status = "failed"
        
        element.annotations.append(LLMTableEnrichmentData(
            llm_markdown_table=markdown_result,
            status=status
        ))
        
        return element

    def __call__(
        self, doc: DoclingDocument, element_batch: Iterable[NodeItem]
    ) -> Iterable[Any]:
        """
        docling pipeline 的主调用函数，处理一批元素。
        
        **多线程实现** (此函数逻辑不变, 它会读取 self.max_workers)
        """
        if not self.enabled:
            return
            
        # 1. 初始化线程池, self.max_workers 会被设置
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            
            # 2. 提交任务
            futures = []
            for element in element_batch:
                if self.is_processable(doc, element):
                    assert isinstance(element, TableItem)
                    log.debug(f"向线程池提交表格 {element.self_ref} 的处理任务")
                    futures.append(
                        executor.submit(self._process_table, doc, element)
                    )

            # 3. 收集结果
            for future in concurrent.futures.as_completed(futures):
                try:
                    processed_element = future.result()
                    yield processed_element
                except Exception as e:
                    log.error(f"多线程处理表格时发生严重错误: {e}", exc_info=True)
                    pass 




