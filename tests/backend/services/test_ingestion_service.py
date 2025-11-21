import pytest
from unittest.mock import MagicMock, AsyncMock

# 导入被测试的类和相关模型
from src.backend.services.ingestion_service import IngestionService
from src.backend.domain.models import DocumentSource, DocumentChunk

# ==========================================
# 测试固件 (Fixtures) - 准备环境
# ==========================================

@pytest.fixture
def mock_dependencies():
    """
    创建所有依赖组件的 Mock 对象。
    """
    # 1. Parser (异步方法 parse)
    # 因为 pipeline 中使用了 await self.parser.parse()，所以这里必须是 AsyncMock
    mock_parser = AsyncMock()
    
    # 2. Splitter (同步方法 split)
    # 虽然 pipeline 中用了 asyncio.to_thread，但 split 本身是同步的，所以用 MagicMock
    mock_splitter = MagicMock()
    
    # 3. Preprocessor (异步方法 run_concurrent_preprocessing)
    mock_preprocessor = AsyncMock()
    
    # 4. Store (异步方法 bulk_add_documents)
    mock_store = AsyncMock()
    
    return mock_parser, mock_splitter, mock_preprocessor, mock_store

@pytest.fixture
def ingestion_service(mock_dependencies):
    """
    实例化 IngestionService，并注入 Mock 依赖。
    """
    parser, splitter, preprocessor, store = mock_dependencies
    return IngestionService(
        parser=parser,
        splitter=splitter,
        preprocessor=preprocessor,
        store=store
    )

@pytest.fixture
def sample_source():
    """创建一个测试用的文档源对象"""
    return DocumentSource(
        file_path="./tmp/test.pdf"
    )

# ==========================================
# 测试用例 (Test Cases)
# ==========================================

@pytest.mark.asyncio
async def test_pipeline_success(ingestion_service, mock_dependencies, sample_source):
    """
    测试用例 1: 快乐路径 (Happy Path)
    验证当所有组件正常工作时，pipeline 能完整跑通。
    """
    parser, splitter, preprocessor, store = mock_dependencies

    # --- 1. 设定 Mock 的行为 (Arrange) ---
    
    # Parser 返回一段 Markdown 文本
    fake_markdown = "# Title\nContent"
    parser.parse.return_value = fake_markdown
    
    # Splitter 返回初始块列表
    # 注意：因为 Splitter 是在 asyncio.to_thread 中调用的，Mock 的返回值就是线程执行的结果
    fake_initial_chunks = [
        DocumentChunk(
            chunk_id="1", 
            document_id="doc_123", 
            document_name="Test Doc",  # <--- 修复点 1: 添加必填字段
            content="Title", 
            parent_headings=[]
        ),
        DocumentChunk(
            chunk_id="2", 
            document_id="doc_123", 
            document_name="Test Doc",  # <--- 修复点 2
            content="Content", 
            parent_headings=[]
        )
    ]
    splitter.split.return_value = fake_initial_chunks
    
    # Preprocessor 返回处理后的块列表 (假设加了摘要)
    fake_enriched_chunks = [
        DocumentChunk(
            chunk_id="1", 
            document_id="doc_123", 
            document_name="Test Doc",  # <--- 修复点 3
            content="Title", 
            summary="Summary1"
        ),
        DocumentChunk(
            chunk_id="2", 
            document_id="doc_123", 
            document_name="Test Doc",  # <--- 修复点 4
            content="Content", 
            summary="Summary2"
        )
    ]
    preprocessor.run_concurrent_preprocessing.return_value = fake_enriched_chunks
    
    # Store 返回 None (void)
    store.bulk_add_documents.return_value = None

    # --- 2. 执行 Pipeline (Act) ---
    await ingestion_service.pipeline(sample_source)

    # --- 3. 验证调用链 (Assert) ---
    
    # 验证 Parser 是否被调用，参数是否正确
    parser.parse.assert_awaited_once_with(sample_source)
    
    # 验证 Splitter 是否被调用
    # 注意：splitter.split 是同步方法，被 to_thread 调用，assert_called_once_with 依然有效
    splitter.split.assert_called_once_with(fake_markdown, sample_source)
    
    # 验证 Preprocessor 是否被调用，且接收了 Splitter 的输出
    preprocessor.run_concurrent_preprocessing.assert_awaited_once_with(fake_initial_chunks)
    
    # 验证 Store 是否被调用，且接收了 Preprocessor 的输出
    store.bulk_add_documents.assert_awaited_once_with(fake_enriched_chunks)


@pytest.mark.asyncio
async def test_pipeline_empty_parse_result(ingestion_service, mock_dependencies, sample_source):
    """
    测试用例 2: 解析结果为空
    验证如果 Parser 返回空字符串，流程是否会提前终止，不调用后续步骤。
    """
    parser, splitter, preprocessor, store = mock_dependencies

    # --- Arrange ---
    parser.parse.return_value = ""  # 返回空字符串

    # --- Act ---
    await ingestion_service.pipeline(sample_source)

    # --- Assert ---
    parser.parse.assert_awaited_once()
    
    # 关键验证：后续步骤不应该被调用
    splitter.split.assert_not_called()
    preprocessor.run_concurrent_preprocessing.assert_not_called()
    store.bulk_add_documents.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_exception_handling(ingestion_service, mock_dependencies, sample_source):
    """
    测试用例 3: 异常处理
    验证如果在 Pipeline 中发生异常（如文件找不到），Service 能够捕获并记录日志，而不是让程序崩溃。
    """
    parser, splitter, _, _ = mock_dependencies

    # --- Arrange ---
    # 模拟 Parser 抛出文件未找到异常
    parser.parse.side_effect = FileNotFoundError("Mock File Not Found")

    # --- Act ---
    # 这里不需要 pytest.raises，因为 pipeline 内部用 try...except 捕获了异常
    await ingestion_service.pipeline(sample_source)

    # --- Assert ---
    parser.parse.assert_awaited_once()
    
    # 验证因为第一步报错，后续步骤未执行
    splitter.split.assert_not_called()