import logging
from typing import List, Tuple
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
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
    
    该类采用两阶段分割策略 (Hybrid Splitting):
    1.  首先使用 MarkdownHeaderTextSplitter 按标题结构进行初次分割。
    2.  然后检查每个块的 token 长度，如果超过 'max_chunk_tokens' 阈值，
        则使用 RecursiveCharacterTextSplitter 对该块进行二次分割。
    """

    def __init__(
        self, 
        headers_to_split_on: List[Tuple[str, str]],
        max_chunk_tokens: int = 1024,
        encoding_name: str = "cl100k_base",
        chunk_overlap_tokens: int = 100
    ):
        """
        初始化 Markdown 分割器。

        Args:
            headers_to_split_on (List[Tuple[str, str]]): 
                用于 MarkdownHeaderTextSplitter 的标题定义。
                示例: [("#", "Header 1"), ("##", "Header 2")]
            max_chunk_tokens (int, optional): 
                最大块 token 长度。超出的块将被二次分割。默认为 1024。
            encoding_name (str, optional): 
                用于计算 token 的 tiktoken 编码器名称。默认为 "cl100k_base"。
            chunk_overlap_tokens (int, optional):
                (二次分割时) 块之间的 token 重叠数。默认为 100。
        """
        super().__init__()
        
        # 1. 初始化 Markdown 标题分割器
        self._md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on, 
            strip_headers=False # 保留标题在内容中，以供上下文参考
        )

        # 2. 初始化 Token 编码器
        try:
            self._tokenizer = tiktoken.get_encoding(encoding_name)
        except ValueError:
            log.warning(f"未找到编码器 '{encoding_name}'，回退到 'gpt2'。")
            self._tokenizer = tiktoken.get_encoding("gpt2")

        self._max_chunk_tokens = max_chunk_tokens

        # 3. 初始化递归字符分割器 (用于二次分割)
        # 使用 from_tiktoken_encoder 来确保 chunk_size 和 chunk_overlap是基于 token 计数的，而不是字符数。
        self._recursive_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=encoding_name,
            chunk_size=max_chunk_tokens,
            chunk_overlap=chunk_overlap_tokens
        )
        
        log.info(
            f"MarkdownSplitter 初始化完毕。最大Tokens: {max_chunk_tokens}，"
            f"重叠Tokens: {chunk_overlap_tokens}，编码器: {encoding_name}"
        )

    def _token_length(self, text: str) -> int:
        """
        辅助方法：计算给定文本的 token 数量。
        
        Args:
            text (str): 输入文本。

        Returns:
            int: 文本对应的 token 数量。
        """
        try:
            return len(self._tokenizer.encode(text))
        except Exception as e:
            log.warning(f"Token 长度计算失败: {e}。对文本: '{text[:50]}...' 返回字符长度。")
            return len(text)

    @staticmethod
    def _extract_parent_headings(metadata: dict) -> List[str]:
        """
        静态辅助方法：从 Langchain 块元数据中提取有序的父标题列表。
        
        此方法用于填充 DocumentChunk.parent_headings 字段。
        
        Args:
            metadata (dict): Langchain Document 块的元数据。
                             (例如 {"Header 1": "主标题", "Header 2": "副标题"})

        Returns:
            List[str]: 有序的标题列表 (例如 ["主标题", "副标题"])。
        """
        # 筛选出所有 'Header X' 键
        headers = {k: v for k, v in metadata.items() if "Header" in k}
        if not headers:
            return []
        
        # 按 'Header 1', 'Header 2' ... 的数字顺序排序
        try:
            sorted_headers = sorted(
                headers.items(), 
                key=lambda x: int(x[0].split()[-1])
            )
        except (ValueError, IndexError):
            log.warning(f"解析标题元数据格式失败: {headers}。返回未排序的值。")
            return list(headers.values())
        
        # 返回排序后的标题值列表
        return [v for _, v in sorted_headers]

    def split(self, markdown_content: str, source: DocumentSource) -> List[DocumentChunk]:
        """
        将Markdown文本分割成 DocumentChunk 列表。
        
        执行两阶段分割：
        1. 按 Markdown 标题分割 (阶段1)。
        2. 对阶段1中 token 长度超标的块，按 token 限制进行递归分割 (阶段2)。

        Args:
            markdown_content (str): 从 DocumentParser 获得的Markdown内容。
            source (DocumentSource): 原始文档信息，用于填充块的元数据。

        Returns:
            List[DocumentChunk]: DocumentChunk 列表。
        """
        log.info(f"开始分割文档: {source.document_name} (ID: {source.document_id})")

        final_chunks: List[DocumentChunk] = []

        # --- 阶段 1: 按 Markdown 标题分割 ---
        # Langchain splitter 返回 List[Document]
        try:
            initial_md_chunks: List[Document] = self._md_splitter.split_text(markdown_content)
        except Exception as e:
            log.error(f"Markdown 标题分割失败 (文档ID: {source.document_id}): {e}", exc_info=True)
            return [] # 失败则返回空列表

        log.debug(f"阶段1 (Markdown标题) 分割完成，产生 {len(initial_md_chunks)} 个初始块。")

        # --- 阶段 2: 检查并按 Token 长度二次分割 ---
        for i, md_chunk in enumerate(initial_md_chunks):
            chunk_content = md_chunk.page_content
            chunk_token_length = self._token_length(chunk_content)
            
            # 提取父标题 (用于 DocumentChunk 的特定字段)
            parent_headings = self._extract_parent_headings(md_chunk.metadata)
            
            # 准备元数据 (合并 langchain splitter 产生的元数据和 source 的元数据)
            chunk_metadata = md_chunk.metadata.copy()
            chunk_metadata.update(source.metadata)
            
            if chunk_token_length <= self._max_chunk_tokens:
                # 块长度达标，直接转换为 DocumentChunk
                log.debug(f"块 {i} (Token: {chunk_token_length}) 长度达标，直接添加。")
                
                final_chunks.append(
                    DocumentChunk(
                        # chunk_id 在模型中自动生成
                        document_id=source.document_id,
                        document_name=source.document_name,
                        content=chunk_content,
                        parent_headings=parent_headings,
                        metadata=chunk_metadata
                    )
                )
            
            else:
                # 块长度超标，需要二次分割
                log.warning(
                    f"块 {i} (Token: {chunk_token_length}) 超出阈值 {self._max_chunk_tokens}，"
                    f"将使用 RecursiveCharacterTextSplitter 进行二次分割。"
                )
                
                # --- 阶段 2 执行 ---
                # 使用 RecursiveCharacterTextSplitter 进行二次分割
                # split_documents 会自动继承 md_chunk 的元数据 (包括标题)
                try:
                    sub_chunks: List[Document] = self._recursive_splitter.split_documents([md_chunk])
                except Exception as e:
                    log.error(f"二次分割失败 (块 {i}, 文档ID: {source.document_id}): {e}", exc_info=True)
                    continue # 跳过这个失败的块

                log.debug(f"块 {i} 被二次分割为 {len(sub_chunks)} 个子块。")

                for sub_chunk in sub_chunks:
                    # 再次检查元数据，确保父标题被正确继承
                    # (Recursive splitter 默认会继承)
                    sub_parent_headings = self._extract_parent_headings(sub_chunk.metadata)
                    
                    # 合并元数据
                    sub_chunk_metadata = sub_chunk.metadata.copy()
                    sub_chunk_metadata.update(source.metadata)

                    final_chunks.append(
                        DocumentChunk(
                            document_id=source.document_id,
                            document_name=source.document_name,
                            content=sub_chunk.page_content,
                            parent_headings=sub_parent_headings,
                            metadata=sub_chunk_metadata
                        )
                    )

        log.info(f"文档 {source.document_name} 分割完毕，共生成 {len(final_chunks)} 个 DocumentChunk。")
        return final_chunks