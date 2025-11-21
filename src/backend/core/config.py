import os
from pathlib import Path
from typing import Literal, List, Tuple, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- 路径配置 ---
# __file__ -> config.py
# .parent -> core/
# .parent -> backend/
# .parent -> src/
# .parent -> Deepresearch/ (项目根目录)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"


class BaseConfigSettings(BaseSettings):
    """
    基础配置类，定义通用的加载行为。
    所有子配置类都应继承此类。
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),      # 指定读取的 .env 文件路径
        env_file_encoding='utf-8',        # 编码格式
        extra="ignore",                   # 忽略环境变量中多余的字段
        frozen=True,                      # 设置为不可变，防止运行时意外修改
        case_sensitive=False,             # 环境变量名大小写不敏感
    )


class DoclingVLMSettings(BaseConfigSettings):
    """
    Docling VLM (视觉语言模型) 相关配置。
    环境变量前缀: DOCLING_VLM_
    例如: DOCLING_VLM_API_KEY 将映射到 api_key
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_prefix="DOCLING_VLM_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    api_key: str
    base_url: str
    model: str
    max_concurrency: int = 3


class DoclingLLMSettings(BaseConfigSettings):
    """
    Docling LLM (文本大模型) 相关配置。
    环境变量前缀: DOCLING_LLM_
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_prefix="DOCLING_LLM_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    api_key: str
    base_url: str
    model: str
    max_concurrency: int = 3


class DoclingGeneralSettings(BaseConfigSettings):
    """
    Docling 通用行为与加速器配置。
    环境变量前缀: DOCLING_
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_prefix="DOCLING_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    # 行为配置
    images_scale: float = 2.0
    do_formula_recognition: bool = True
    do_table_enrichment: bool = True
    do_pic_enrichment: bool = True
    do_ocr: bool = False

    # 加速器设置
    # 对应原配置中的 DOCLING_ACCELERATOR_DEVICE 和 DOCLING_ACCELERATOR_NUM_THREADS
    accelerator_device: str = "CPU"
    accelerator_num_threads: int = 4


class TextSplitterSettings(BaseConfigSettings):
    """
    文本分块 (Splitter) 配置。
    由于原配置没有统一前缀，这里使用 alias (别名) 映射到原有的环境变量名。
    """
    # 对应原配置 MAX_CHUNK_TOKENS
    max_chunk_tokens: int = Field(default=1024, validation_alias="MAX_CHUNK_TOKENS")
    # 对应原配置 ENCODING_NAME
    encoding_name: str = Field(default="cl100k_base", validation_alias="ENCODING_NAME")
    # 对应原配置 CHUNK_OVERLAP_TOKENS
    chunk_overlap_tokens: int = Field(default=100, validation_alias="CHUNK_OVERLAP_TOKENS")
    
    # 标题分割规则
    headers_to_split_on: List[Tuple[str, str]] = Field(
        default=[
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
            ("####", "Header 4"),
            ("#####", "Header 5"),
            ("######", "Header 6"),
            ("#######", "Header 7"),
            ("########", "Header 8")
        ],
        validation_alias="HEADERS_TO_SPLIT_ON"
    )


class PreprocessingLLMSettings(BaseConfigSettings):
    """
    文本块预处理 LLM 配置。
    环境变量前缀: PREPROCESSING_LLM_
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_prefix="PREPROCESSING_LLM_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    api_key: str
    base_url: str
    model: str
    max_concurrency: int = 3


class EmbeddingLLMSettings(BaseConfigSettings):
    """
    Embedding (向量化) 模型配置。
    环境变量前缀: EMBEDDING_LLM_
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_prefix="EMBEDDING_LLM_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    api_key: str
    base_url: str
    model: str
    dimension: int = 2560
    max_concurrency: int = 5


class RewriteLLMSettings(BaseConfigSettings):
    """
    Query Rewrite (查询重写) LLM 配置。
    环境变量前缀: REWRITE_LLM_
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_prefix="REWRITE_LLM_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    api_key: str
    base_url: str
    model: str
    max_concurrency: int = 30


class TeiRerankSettings(BaseConfigSettings):
    """
    TEI (Text Embeddings Inference) Reranker 重排序配置。
    环境变量前缀: TEI_RERANK_
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_prefix="TEI_RERANK_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    base_url: str = "http://localhost:8082"
    api_key: Optional[str] = None
    max_concurrency: int = 50
    timeout: float = 30.0


class OpenSearchSettings(BaseConfigSettings):
    """
    OpenSearch 向量数据库配置。
    环境变量前缀: OPENSEARCH_
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_prefix="OPENSEARCH_",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    index_name: str = "rag_system_chunks_async"
    host: str = 'localhost'
    port: int = 9200
    
    # 注意：原代码中变量名为 AUTH，没有 OPENSEARCH_ 前缀
    # 这里使用 alias 将其映射回原始的 AUTH 环境变量
    auth: str = Field(default='admin:admin', validation_alias="AUTH")
    
    use_ssl: bool = False
    verify_certs: bool = False
    bulk_chunk_size: int = 500


class Settings(BaseConfigSettings):
    """
    主配置类，聚合所有子配置。
    Pydantic V2 会自动管理这些嵌套配置。
    """
    # --- 全局/顶层配置 ---
    
    # 日志级别 (对应原配置 LOG_LEVEL)
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    
    # LiteLLM 代理 (从 .env 加载 LITELLM_PROXY_URL)
    litellm_proxy_url: str = Field(validation_alias="LITELLM_PROXY_URL")

    # --- 子模块配置 (使用 default_factory 初始化) ---
    
    docling_vlm: DoclingVLMSettings = Field(default_factory=DoclingVLMSettings)
    docling_llm: DoclingLLMSettings = Field(default_factory=DoclingLLMSettings)
    docling_general: DoclingGeneralSettings = Field(default_factory=DoclingGeneralSettings)
    
    splitter: TextSplitterSettings = Field(default_factory=TextSplitterSettings)
    
    preprocessing_llm: PreprocessingLLMSettings = Field(default_factory=PreprocessingLLMSettings)
    embedding_llm: EmbeddingLLMSettings = Field(default_factory=EmbeddingLLMSettings)
    rewrite_llm: RewriteLLMSettings = Field(default_factory=RewriteLLMSettings)
    
    tei_rerank: TeiRerankSettings = Field(default_factory=TeiRerankSettings)
    opensearch: OpenSearchSettings = Field(default_factory=OpenSearchSettings)


# --- 全局设置实例 ---
# 其他模块应通过 `from .core.config import settings` 导入使用
# 使用方式示例: settings.opensearch.host, settings.docling_vlm.api_key

try:
    settings = Settings()

except Exception as e:
    print(f"!!! 严重错误: 无法从 {ENV_FILE_PATH} 加载配置。")
    print(f"错误详情: {e}")
    # 打印更详细的错误以便调试 (通常是缺少必要的环境变量)
    if "validation error" in str(e).lower():
        print("提示: 请检查 .env 文件中是否包含所有必需的 API KEY 和 URL 配置。")
    raise e