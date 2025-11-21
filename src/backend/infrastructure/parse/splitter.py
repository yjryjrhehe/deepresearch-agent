import logging
from typing import List, Tuple
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_core.documents import Document
import tiktoken

from ...domain.interfaces import TextSplitter
from ...domain.models import DocumentChunk, DocumentSource
from ...core.logging import setup_logging

# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)


class MarkdownSplitter(TextSplitter):
    """
    实现 TextSplitter 接口，用于分割 Markdown 文本。
    """

    def __init__(
        self,
        headers_to_split_on: List[Tuple[str, str]],
        max_chunk_tokens: int = 1024,
        chunk_overlap_tokens: int = 100,
        encoding_name: str = "cl100k_base"
    ):
        """
        初始化 Markdown 分割器。
        
        参数由工厂方法注入，解耦了具体的配置源。

        Args:
            headers_to_split_on: 用于 MarkdownHeaderTextSplitter 的标题定义。
            max_chunk_tokens: 最大块 token 长度。
            chunk_overlap_tokens: 二次分割时的重叠 token 数。
            encoding_name: tiktoken 编码器名称。
        """
        super().__init__()
        
        self._max_chunk_tokens = max_chunk_tokens
        self._encoding_name = encoding_name

        # 1. 初始化 Markdown 标题分割器
        self._md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False,  # 保留标题在内容中
        )

        # 2. 初始化 Token 编码器
        try:
            self._tokenizer = tiktoken.get_encoding(encoding_name)
        except ValueError:
            log.warning(f"未找到编码器 '{encoding_name}'，回退到 'gpt2'。")
            self._tokenizer = tiktoken.get_encoding("gpt2")

        # 3. 初始化递归字符分割器 (用于二次分割)
        self._recursive_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=encoding_name,
            chunk_size=max_chunk_tokens,
            chunk_overlap=chunk_overlap_tokens,
        )

        log.info(
            f"MarkdownSplitter 初始化完毕。最大Tokens: {max_chunk_tokens}，"
            f"重叠Tokens: {chunk_overlap_tokens}，编码器: {encoding_name}"
        )

    def _token_length(self, text: str) -> int:
        """辅助方法：计算 token 数量"""
        try:
            return len(self._tokenizer.encode(text))
        except Exception as e:
            log.warning(f"Token 长度计算失败: {e}。返回字符长度。")
            return len(text)

    @staticmethod
    def _extract_parent_headings(metadata: dict) -> List[str]:
        """辅助方法：提取标题列表"""
        headers = {k: v for k, v in metadata.items() if "Header" in k}
        if not headers:
            return []
        try:
            sorted_headers = sorted(
                headers.items(), key=lambda x: int(x[0].split()[-1])
            )
        except (ValueError, IndexError):
            return list(headers.values())
        return [v for _, v in sorted_headers]

    def split(
        self, markdown_content: str, source: DocumentSource
    ) -> List[DocumentChunk]:
        """
        将Markdown文本分割成 DocumentChunk 列表。
        """
        log.info(f"开始分割文档: {source.document_name} (ID: {source.document_id})")

        final_chunks: List[DocumentChunk] = []

        # --- 阶段 1: 按 Markdown 标题分割 ---
        try:
            initial_md_chunks: List[Document] = self._md_splitter.split_text(
                markdown_content
            )
        except Exception as e:
            log.error(f"Markdown 标题分割失败: {e}", exc_info=True)
            return [] 

        # --- 阶段 2: 检查并按 Token 长度二次分割 ---
        for i, md_chunk in enumerate(initial_md_chunks):
            chunk_content = md_chunk.page_content
            chunk_token_length = self._token_length(chunk_content)

            parent_headings = self._extract_parent_headings(md_chunk.metadata)
            chunk_metadata = md_chunk.metadata.copy()
            chunk_metadata.update(source.metadata)

            if chunk_token_length <= self._max_chunk_tokens:
                # 长度达标，直接添加
                final_chunks.append(
                    DocumentChunk(
                        document_id=source.document_id,
                        document_name=source.document_name,
                        content=chunk_content,
                        parent_headings=parent_headings,
                        metadata=chunk_metadata,
                    )
                )
            else:
                # 长度超标，递归分割
                log.warning(
                    f"块 {i} (Token: {chunk_token_length}) 超出阈值，进行二次分割。"
                )
                try:
                    sub_chunks: List[Document] = (
                        self._recursive_splitter.split_documents([md_chunk])
                    )
                except Exception as e:
                    log.error(f"二次分割失败 (块 {i}): {e}", exc_info=True)
                    continue 

                for sub_chunk in sub_chunks:
                    sub_parent_headings = self._extract_parent_headings(sub_chunk.metadata)
                    sub_chunk_metadata = sub_chunk.metadata.copy()
                    sub_chunk_metadata.update(source.metadata)

                    final_chunks.append(
                        DocumentChunk(
                            document_id=source.document_id,
                            document_name=source.document_name,
                            content=sub_chunk.page_content,
                            parent_headings=sub_parent_headings,
                            metadata=sub_chunk_metadata,
                        )
                    )

        log.info(f"文档 {source.document_name} 分割完毕，生成 {len(final_chunks)} 个块。")
        return final_chunks