# === 步骤 1: 导入所需库 ===
import logging
import base64
from io import BytesIO
from collections.abc import Iterable
from typing import Any

from openai import OpenAI  # 用于 VLM API 调用
from PIL import Image  # 用于处理图像
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- docling 核心库 ---
# docling_core 定义了文档的基本结构
from docling_core.types.doc import (
    DoclingDocument,
    NodeItem,
    PictureItem,
    DescriptionAnnotation
)

from docling.models.base_model import BaseEnrichmentModel

from ..prompt.VLM_prompt import VLM_PROMPT
from ..vlm_enrichment_pipeline_options import VLMEnrichmentPipelineOptions
from ....core.logging import setup_logging 

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)

class VLMPictureEnrichmentModel(BaseEnrichmentModel):
    """
    一个 docling 增强模型，用于为 PictureItem 添加 VLM 生成的描述。
    使用 ThreadPoolExecutor 并行处理 VLM API 调用。
    """
    
    def __init__(self, options: VLMEnrichmentPipelineOptions):
        """
        初始化模型。

        Args:
            options: 包含 VLM 配置的 PipelineOptions。
        """
        super().__init__() 
        self.enabled = options.do_pic_enrichment

        self.api_key = options.vlm_api_key
        self.base_url = options.vlm_base_url
        self.model = options.vlm_model

        # 从 options 中读取最大并发数
        self.max_concurrency = options.vlm_max_concurrency

    def is_processable(self, doc: DoclingDocument, element: NodeItem) -> bool:
        """
        检查此模型是否应处理给定的元素。
        """
        return self.enabled and isinstance(element, PictureItem)

    def _call_vlm_for_description(self, pil_image: Image.Image, prompt: str=VLM_PROMPT) -> str:
        """
        使用 VLM  API 为给定的 PIL 图像生成描述。

        Args:
            pil_image: 待描述的 PIL.Image.Image 对象。
            prompt: 发送给 VLM 的提示词。

        Returns:
            VLM 返回的图像描述文本。
            
        Raises:
            Exception: 如果 API 调用失败。
        """
        log.info(f"正在调用 VLM (模型: {self.model}) 为图像生成描述...")
        try:
            # 1. 将 PIL Image 转换为 Base64
            buffered = BytesIO()
            # 检查图像是否为 RGBA 模式（或其他带 Alpha 通道的模式）
            if pil_image.mode in ("RGBA", "LA", "P"):
                # 转换为 RGB 模式，丢弃 Alpha 通道
                # 这通常会将透明背景变为白色
                log.debug(f"检测到 {pil_image.mode} 图像，正在转换为 RGB...")
                pil_image = pil_image.convert('RGB')
                
            pil_image.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # 2. 初始化 OpenAI 客户端 (适配通义千问等VLM)
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            # 3. 构造消息体
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
            ]
            
            # 4. 发送 API 请求
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}]
            )
            
            description = completion.choices[0].message.content.strip()
            log.info("VLM 描述生成成功。")
            return description
            
        except Exception as e:
            log.warning(f"VLM 图像描述 API 失败: {e}")
            raise

    
    def __call__(
        self, doc: DoclingDocument, element_batch: Iterable[NodeItem]
    ) -> Iterable[Any]:
        """
        处理一批元素 (由 docling 传入)，使用多线程并行处理 VLM Call。
        """
        # 1. 检查 VLM 是否被禁用
        if not self.enabled:
            return

        # 2. 准备线程池和任务映射
        #    futures_map 用于将 Future 对象映射回它所属的 docling 元素 (element)
        futures_map = {}
        
        with ThreadPoolExecutor(
            max_workers=self.max_concurrency, 
            thread_name_prefix="VLM_Picture_Worker"
        ) as executor:
            
            # 3. 提交任务
            #    遍历 docling 传来的元素批次
            log.info(f"开始提交 VLM 任务，最大并发数: {self.max_concurrency}")
            for element in element_batch:
                if not self.is_processable(doc, element):
                    # --- A. 非处理目标 (例如文本、表格等) ---
                    # 如果元素不是 PictureItem，
                    # 立刻将其 yield，不做任何处理，
                    # 以保持其在文档流中的原始位置。
                    yield element
                    continue
                
                # --- B. 处理目标 (PictureItem) ---
                assert isinstance(element, PictureItem)
                
                try:
                    # (a) 从 docling 获取 PictureItem 的 PIL 图像
                    pil_img = element.get_image(doc)
                    if pil_img is None:
                        log.warning(f"获取 PictureItem {element.self_ref} 的图像失败 (返回 None)，跳过此项。")
                        yield element # 仍然 yield，防止丢失
                        continue

                    log.debug(f"正在提交 PictureItem {element.self_ref} 到 VLM 任务队列...")
                    
                    # (b) 提交 VLM 任务到线程池
                    future = executor.submit(
                        self._call_vlm_for_description, # 要调用的函数
                        pil_image=pil_img,      # --- 以下是函数的参数 ---
                        prompt=VLM_PROMPT,
                    )
                    
                    # (c) 存储 future 和 element 的映射关系
                    futures_map[future] = element
                    
                except Exception as e:
                    # 如果在 *提交前* (例如 get_image 失败)
                    log.error(f"处理 PictureItem {element.self_ref} 时出错 (提交前): {e}")
                    # 仍然 yield 原始 element，防止其丢失
                    yield element
            
            # 4. 处理已完成的任务 (按完成顺序)
            #    如果 futures_map 为空 (即没有 PictureItem 被提交)，这个循环将被跳过。
            if not futures_map:
                log.info("VLM 批处理完成 (没有需要处理的图片)。")
                return
                
            log.info(f"已提交 {len(futures_map)} 个 VLM 任务，等待完成...")

            for future in as_completed(futures_map.keys()):
                # (a) 获取任务对应的原始 element
                element = futures_map[future] 
                
                try:
                    # (b) 获取 VLM 线程的返回结果 (description)
                    #     如果 VLM 调用在线程中失败，.result() 会重新抛出该异常
                    description = future.result() 
                    log.info(f"VLM 任务成功 (PictureItem {element.self_ref})")

                    # (c) 将结果附加到 element 上
                    element.annotations.append(
                        DescriptionAnnotation(
                            provenance=self.model,
                            text=description
                        )
                    )
                    
                except Exception as e:
                    # (d) 处理 VLM 任务执行期间的异常
                    log.error(f"VLM 任务失败 (PictureItem {element.self_ref}): {e}")
                
                finally:
                    yield element
        
        log.info("VLM 批处理全部完成。")




