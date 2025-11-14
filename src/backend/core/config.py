from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# --- 路径配置 ---
# (定位到项目根目录)
# __file__ -> config.py
# .parent -> core/
# .parent -> backend/
# .parent -> src/
# .parent -> Deepresearch/ (项目根目录)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    """
    管理所有应用设置。
    Pydantic V2 会自动从 .env 文件和环境变量中加载配置。
    """
    # (新增) 日志级别设置
    LOG_LEVEL: str = "INFO"

    # --- LiteLLM 代理 (用于 Agent/RAG 服务) ---
    # (从 .env 加载)
    LITELLM_PROXY_URL: str

    # ---------------------------------------------------------
    # ↓↓↓ 新增: Docling 解析器配置 (从 .env 加载) ↓↓↓
    # ---------------------------------------------------------
    
    # --- 3. Docling VLM (视觉) 密钥与端点 ---
    DOCLING_VLM_API_KEY: str
    DOCLING_VLM_BASE_URL: str
    DOCLING_VLM_MODEL: str
    DOCLING_VLM_MAX_CONCURRENCY: int = 3

    # --- 4. Docling LLM (文本) 密钥与端点 ---
    DOCLING_LLM_API_KEY: str
    DOCLING_LLM_BASE_URL: str
    DOCLING_LLM_MODEL: str
    DOCLING_LLM_MAX_CONCURRENCY: int = 3

    # --- 5. Docling 行为配置 (提供默认值) ---
    
    DOCLING_IMAGES_SCALE: float = 2.0
    DOCLING_DO_FORMULA_RECOGNITION: bool = True
    DOCLING_DO_TABLE_ENRICHMENT: bool = True
    DOCLING_DO_PIC_ENRICHMENT: bool = True
    DOCLING_DO_OCR: bool = False
    
    # Docling 加速器设置
    # (从 'AcceleratorDevice.CPU' 提取)
    DOCLING_ACCELERATOR_DEVICE: str = "CPU" 
    # (从 'num_threads=4' 提取)
    DOCLING_ACCELERATOR_NUM_THREADS: int = 4

    # 文本块预处理LLM配置
    PREPROCESSING_LLM_API_KEY: str
    PREPROCESSING_LLM_BASE_URL: str
    PREPROCESSING_LLM_MODEL: str
    PREPROCESSING_LLM_MAX_CONCURRENCY: int = 3

    # --- Pydantic v2 模型配置 ---
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), # 明确指定 .env 文件路径
        env_file_encoding='utf-8',
        extra='ignore'  # 忽略 .env 中多余的变量 (如 DEEPRESEARCH_...)
    )

# --- 全局设置实例 ---
# 所有其他地方都应该 `from .core.config import settings`

try:
    settings = Settings()

except Exception as e:
    print(f"!!! 严重错误: 无法从 {ENV_FILE_PATH} 加载配置。")
    print(f"错误详情: {e}")
    raise e