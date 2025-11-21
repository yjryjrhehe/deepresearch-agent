import pytest
from unittest.mock import MagicMock, patch

from src.backend.services.factory import get_ingestion_service

@pytest.fixture(autouse=True)
def clear_lru_cache():
    """
    Pytest Fixture: 自动在每个测试用例执行前/后清理 lru_cache。
    这是必须的！因为 get_ingestion_service 是单例，
    如果不清理，第二个测试会直接读取第一个测试的缓存结果，导致 Mock 断言失败。
    """
    get_ingestion_service.cache_clear()
    yield
    get_ingestion_service.cache_clear()

# 使用 patch 模拟 factory.py 中导入的所有依赖函数和类
# 注意 patch 的路径必须是 "src.backend.services.factory.xxx" (即它们被使用的地方)
@patch("src.backend.services.factory.get_opensearch_store")
@patch("src.backend.services.factory.get_llm_preprocessor")
@patch("src.backend.services.factory.get_markdown_splitter")
@patch("src.backend.services.factory.get_docling_parser")
@patch("src.backend.services.factory.IngestionService") # 模拟 Service 类本身
def test_get_ingestion_service_success(
    mock_service_class,
    mock_get_parser,
    mock_get_splitter,
    mock_get_preprocessor,
    mock_get_store
):
    """
    测试用例 1: 验证工厂能正确获取依赖并组装 Service
    """
    # --- 1. 准备 (Arrange) ---
    # 创建模拟的组件实例
    parser_instance = MagicMock(name="ParserInstance")
    splitter_instance = MagicMock(name="SplitterInstance")
    preprocessor_instance = MagicMock(name="PreprocessorInstance")
    store_instance = MagicMock(name="StoreInstance")
    service_instance = MagicMock(name="IngestionServiceInstance")

    # 让模拟的工厂函数返回上面创建的模拟实例
    mock_get_parser.return_value = parser_instance
    mock_get_splitter.return_value = splitter_instance
    mock_get_preprocessor.return_value = preprocessor_instance
    mock_get_store.return_value = store_instance
    
    # 让模拟的 IngestionService 类构造函数返回模拟的 service 实例
    mock_service_class.return_value = service_instance

    # --- 2. 执行 (Act) ---
    result = get_ingestion_service()

    # --- 3. 断言 (Assert) ---
    
    # 断言 1: 返回的对象是我们模拟的 Service 实例
    assert result == service_instance

    # 断言 2: 所有的底层工厂函数都被调用了一次
    mock_get_parser.assert_called_once()
    mock_get_splitter.assert_called_once()
    mock_get_preprocessor.assert_called_once()
    mock_get_store.assert_called_once()

    # 断言 3: IngestionService 被正确初始化，且传入了正确的依赖参数
    # 这一步是核心：验证依赖注入逻辑是否正确
    mock_service_class.assert_called_once_with(
        parser=parser_instance,
        splitter=splitter_instance,
        preprocessor=preprocessor_instance,
        store=store_instance
    )

@patch("src.backend.services.factory.get_docling_parser")
# 我们只需要 mock 一个依赖来模拟报错即可，其他的可以简写
def test_get_ingestion_service_dependency_failure(mock_get_parser):
    """
    测试用例 2: 验证当某个依赖初始化失败时，工厂方法能正确处理异常
    """
    # --- 1. 准备 ---
    # 模拟获取 parser 时抛出异常
    mock_get_parser.side_effect = Exception("Database connection failed")

    # --- 2. 执行 & 断言 ---
    # 验证工厂方法抛出了异常（且通过 try-except 记录了日志后重新抛出）
    with pytest.raises(Exception) as excinfo:
        get_ingestion_service()
    
    assert "Database connection failed" in str(excinfo.value)

@patch("src.backend.services.factory.get_opensearch_store")
@patch("src.backend.services.factory.get_llm_preprocessor")
@patch("src.backend.services.factory.get_markdown_splitter")
@patch("src.backend.services.factory.get_docling_parser")
@patch("src.backend.services.factory.IngestionService")
def test_get_ingestion_service_singleton_behavior(
    mock_service_class,
    mock_get_parser,
    mock_get_splitter,
    mock_get_preprocessor,
    mock_get_store
):
    """
    测试用例 3: 验证 @lru_cache 单例行为
    """
    # --- 第一次调用 ---
    service1 = get_ingestion_service()
    
    # --- 第二次调用 ---
    service2 = get_ingestion_service()

    # --- 断言 ---
    # 1. 两次返回的是同一个对象实例
    assert service1 is service2
    
    # 2. 底层工厂函数只被调用了一次（证明走了缓存）
    mock_get_parser.assert_called_once()
    # 如果没有缓存，这里应该是 call_count == 2