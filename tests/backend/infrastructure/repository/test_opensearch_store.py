import pytest
from unittest.mock import AsyncMock, patch

# 导入被测试的类和相关模型
from src.backend.infrastructure.repository.opensearch_store import AsyncOpenSearchRAGStore
from src.backend.domain.models import DocumentChunk, RetrievedChunk

# ==========================================
# Test Fixtures (环境准备)
# ==========================================

@pytest.fixture
def mock_opensearch_client():
    """创建一个模拟的 OpenSearch 客户端"""
    client = AsyncMock()
    # 模拟 ping 方法返回 True，表示连接正常
    client.ping.return_value = True
    return client

@pytest.fixture
def mock_embedding_client():
    """创建一个模拟的 Embedding 客户端"""
    client = AsyncMock()
    # 模拟 aembed_query 返回一个固定长度的向量
    client.aembed_query.return_value = [0.1] * 1536
    return client

@pytest.fixture
def rag_store(mock_opensearch_client, mock_embedding_client):
    """
    初始化 AsyncOpenSearchRAGStore，并 Patch 掉所有的外部依赖。
    """
    # Patch 路径必须指向 opensearch_store.py 中导入这些类的地方
    with patch("src.backend.infrastructure.repository.opensearch_store.AsyncOpenSearch", return_value=mock_opensearch_client), \
         patch("src.backend.infrastructure.repository.opensearch_store.get_embedding_model", return_value=mock_embedding_client), \
         patch("src.backend.infrastructure.repository.opensearch_store.settings") as mock_settings:
        
        # 设置模拟配置
        mock_settings.opensearch.index_name = "test_rag_index"
        mock_settings.opensearch.host = "localhost"
        mock_settings.opensearch.port = 9200
        mock_settings.opensearch.auth = "admin:admin"
        mock_settings.opensearch.use_ssl = False
        mock_settings.opensearch.verify_certs = False
        mock_settings.embedding_llm.dimension = 1536
        
        # 实例化 Store
        store = AsyncOpenSearchRAGStore()
        return store

# ==========================================
# Unit Tests (单元测试)
# ==========================================

def test_convert_to_retrieved_chunk(rag_store):
    """
    测试 _convert_to_retrieved_chunk 方法：
    验证是否能正确地将 OpenSearch 的 source 字典转换为 RetrievedChunk 对象。
    """
    # Arrange
    mock_source = {
        "chunk_id": "chunk_123",
        "document_id": "doc_ABC",
        "document_name": "test_doc.pdf",
        "content": "This is test content.",
        "summary": "This is a summary.",
        "metadata": {"page": 1}
    }
    mock_score = 0.85

    # Act
    result = rag_store._convert_to_retrieved_chunk(mock_source, mock_score)

    # Assert
    assert isinstance(result, RetrievedChunk)
    assert result.chunk.chunk_id == "chunk_123"
    assert result.chunk.content == "This is test content."
    # 验证 search_score 被正确赋值
    assert result.search_score == 0.85
    # 验证 rerank_score 初始为 None
    assert result.rerank_score is None

def test_rrf_fuse(rag_store):
    """
    测试 _rrf_fuse 方法：
    验证 RRF (Reciprocal Rank Fusion) 算法逻辑及返回格式。
    """
    # Arrange
    # 模拟两路召回结果
    # List 1: doc1 (rank 1), doc2 (rank 2)
    list1 = [{"_id": "doc1"}, {"_id": "doc2"}]
    # List 2: doc2 (rank 1), doc3 (rank 2)
    list2 = [{"_id": "doc2"}, {"_id": "doc3"}]
    
    # 使用简单的 k=1 方便手动计算
    # doc1 score = 1/(1+1) = 0.5
    # doc2 score = 1/(1+2) + 1/(1+1) = 0.333 + 0.5 = 0.833
    # doc3 score = 1/(1+2) = 0.333
    k_constant = 1

    # Act
    fused_results = rag_store._rrf_fuse([list1, list2], k_constant=k_constant)

    # Assert
    # 1. 验证返回类型是 List[Tuple[str, float]]
    assert isinstance(fused_results, list)
    assert isinstance(fused_results[0], tuple)
    
    # 2. 验证排序顺序：应该 doc2 分数最高，排第一
    assert fused_results[0][0] == "doc2"
    assert fused_results[1][0] == "doc1"
    assert fused_results[2][0] == "doc3"
    
    # 3. 验证分数大小关系
    assert fused_results[0][1] > fused_results[1][1]
    
@pytest.mark.asyncio
async def test_hybrid_search_success(rag_store):
    """
    测试 hybrid_search 方法：
    验证整个混合搜索流程（Embedding -> 5路搜索 -> RRF -> mget -> 结果组装）。
    """
    # --- Arrange (Mock 内部方法调用) ---
    # 1. Mock BM25 搜索结果
    rag_store.bm25_search = AsyncMock(return_value=[{"_id": "doc1"}])
    
    # 2. Mock 向量搜索结果 (模拟4次调用都返回相同结果以便简化)
    rag_store._base_vector_search = AsyncMock(return_value=[{"_id": "doc1"}])
    
    # 3. Mock Embedding 生成 (在 fixture 中已设置，但这里确认一下)
    rag_store._get_embedding_async = AsyncMock(return_value=[0.1]*1536)
    
    # 4. Mock mget (获取文档详情)
    # 这是关键：模拟数据库返回了 source 数据
    rag_store.client.mget.return_value = {
        "docs": [
            {
                "_id": "doc1",
                "found": True,
                "_source": {
                    "chunk_id": "doc1",
                    "document_id": "d1",
                    "content": "Mock Content",
                    "document_name": "Mock Doc"
                }
            }
        ]
    }

    # --- Act ---
    results = await rag_store.hybrid_search("test query", k=5)

    # --- Assert ---
    assert len(results) == 1
    item = results[0]
    
    # 验证返回的是 RetrievedChunk 类型
    assert isinstance(item, RetrievedChunk)
    # 验证数据填充正确
    assert item.chunk.chunk_id == "doc1"
    assert item.chunk.content == "Mock Content"
    # 验证分数存在 (RRF 分数)
    assert item.search_score > 0

@pytest.mark.asyncio
async def test_hybrid_search_empty_query(rag_store):
    """测试空查询直接返回空列表"""
    results = await rag_store.hybrid_search("")
    assert results == []

@pytest.mark.asyncio
async def test_hybrid_search_batch(rag_store):
    """
    测试 hybrid_search_batch 方法：
    验证是否能并发处理多个查询并返回正确的嵌套列表结构。
    """
    # Arrange
    # Mock 单次搜索，让它返回一个假的 RetrievedChunk
    fake_chunk = RetrievedChunk(
        chunk=DocumentChunk(chunk_id="1", document_id="d1", content="c", document_name="d"),
        search_score=0.9
    )
    rag_store.hybrid_search = AsyncMock(return_value=[fake_chunk])
    
    queries = ["query1", "query2"]

    # Act
    results = await rag_store.hybrid_search_batch(queries)

    # Assert
    # 应该是 List[List[RetrievedChunk]]，且长度为 2
    assert len(results) == 2
    assert len(results[0]) == 1
    assert results[0][0] == fake_chunk
    
    # 验证 hybrid_search 被调用了两次
    assert rag_store.hybrid_search.call_count == 2