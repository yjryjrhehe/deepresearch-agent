import logging
from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 导入标准接口和数据模型
from ...domain.interfaces import Retriever, SearchRepository
from ...domain.models import RetrievedChunk
from ..llm.reranker import TEIRerankerClient

# 初始化日志
log = logging.getLogger(__name__)

class RetrievalService(Retriever):
    """
    文档检索服务实现类 (业务流程编排)。
    负责协调 Query Rewrite -> Parallel Hybrid Search -> Deduplication -> Rerank 流程。
    """

    def __init__(
        self,
        search_repo: SearchRepository,
        rewrite_llm,
        rerank_client: TEIRerankerClient
    ):
        self.search_repo = search_repo
        self.rewrite_llm = rewrite_llm
        self.rerank_client = rerank_client
        
        # 定义查询改写的 Prompt
        self.rewrite_prompt = ChatPromptTemplate.from_template(
            """你是一个专业的搜索助手。请根据用户的原始问题，生成 3 个相关的搜索查询变体，以便更好地在知识库中检索信息。
            
            原始问题: {question}
            
            要求：
            1. 变体应涵盖原始问题的不同角度或关键词。
            2. 仅输出查询变体，每行一个。
            3. 不要输出序号或额外的解释性文字。
            """
        )
        self.rewrite_chain = self.rewrite_prompt | self.rewrite_llm | StrOutputParser()

    async def _rewrite_query(self, query: str) -> List[str]:
        """
        使用 LLM 生成查询变体。
        """
        try:
            # 调用 LLM 生成变体
            result = await self.rewrite_chain.ainvoke({"question": query})
            # 按行分割并清洗
            rewritten_queries = [line.strip() for line in result.split('\n') if line.strip()]
            log.info(f"查询改写完成，原始: '{query}', 变体: {rewritten_queries}")
            return rewritten_queries
        except Exception as e:
            log.error(f"查询改写失败，将仅使用原始查询: {e}")
            return []

    async def _execute_parallel_search(self, queries: List[str]) -> List[RetrievedChunk]:
        """
        并发执行多路检索。
        直接利用 SearchRepository 提供的批量接口，减少 Service 层复杂度。
        """
        if not queries:
            return []

        try:
            # 直接调用 Repository 的批量接口
            # 返回类型是 List[List[RetrievedChunk]]
            batch_results = await self.search_repo.hybrid_search_batch(
                queries=queries, 
                k=10, 
                rrf_k=60
            )
            
            # 展平结果 (Flatten): List[List] -> List
            # 将所有查询（原始+变体）检索到的结果合并到一个列表中
            flat_results = [
                chunk 
                for sublist in batch_results 
                for chunk in sublist
            ]
            
            log.info(f"批量检索完成，共 {len(queries)} 个查询，累计召回 {len(flat_results)} 个文档块")
            return flat_results
            
        except Exception as e:
            log.error(f"执行批量检索时发生错误: {e}", exc_info=True)
            return []

    def _deduplicate_results(self, chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """
        对检索结果进行去重。
        策略：保留 chunk_id 相同的文档中 search_score 最高的那一个。
        """
        unique_map: Dict[str, RetrievedChunk] = {}
        
        for chunk in chunks:
            c_id = chunk.chunk.chunk_id
            if c_id not in unique_map:
                unique_map[c_id] = chunk
            else:
                # 如果已存在，保留分数更高的
                if chunk.search_score > unique_map[c_id].search_score:
                    unique_map[c_id] = chunk
                    
        deduplicated = list(unique_map.values())
        log.debug(f"去重完成: 输入 {len(chunks)} -> 输出 {len(deduplicated)}")
        return deduplicated

    async def retrieve(self, query: str) -> List[RetrievedChunk]:
        """
        编排完整的 RAG 检索流程。
        1. 调用 rewrite_client 改写查询
        2. 并发调用 SearchRepository.hybrid_search
        3. 聚合、去重
        4. 调用 rerank_client 重排序
        5. 返回最终列表
        """
        log.info(f"--- 开始检索流程，用户查询: {query} ---")

        # 1. 查询改写 (Step 1: Query Rewriting)
        # 原始查询必须保留
        queries = [query]
        rewritten = await self._rewrite_query(query)
        queries.extend(rewritten)

        # 2. 并发检索 (Step 2: Parallel Search)
        raw_chunks = await self._execute_parallel_search(queries)
        
        if not raw_chunks:
            log.warning("所有检索路径均未返回结果。")
            return []

        # 3. 聚合去重 (Step 3: Deduplication)
        unique_chunks = self._deduplicate_results(raw_chunks)

        # 4. 重排序 (Step 4: Rerank)
        # 注意：重排序通常使用用户的“原始查询”来衡量相关性，而不是改写后的查询
        try:
            # 假设我们需要 Top 8 的最终结果
            reranked_chunks = await self.rerank_client.arerank(
                query=query,
                chunks=unique_chunks,
                top_n=8,
                truncate=True
            )
            log.info(f"重排序完成，返回 Top-{len(reranked_chunks)} 结果")
            return reranked_chunks
            
        except Exception as e:
            log.error(f"重排序服务调用失败，降级为返回按搜索分数排序的结果: {e}", exc_info=True)
            # 降级策略：如果 Rerank 挂了，按原始 search_score 排序并截断
            unique_chunks.sort(key=lambda x: x.search_score, reverse=True)
            return unique_chunks[:8]

