from functools import lru_cache
from langfuse import Langfuse
import logging

from ...core.logging import setup_logging

# === 日志配置 ===
setup_logging() 
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1) 
def init_langfuse_client(public_key: str, secret_key: str, base_url: str):
    """
    初始化 Langfuse 客户端 (单例/缓存模式)
    参数必须是 hashable 的 (str), 不能传 Pydantic 对象
    """
    try:
        # 只有当 key 存在时才初始化
        if public_key and secret_key:
            logger.info("正在初始化langfuse客户端......")
            return Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                base_url=base_url
            )
        return None
    except Exception as e:
        logger.warning(f"Langfuse 初始化失败，将使用本地 Prompt: {e}")
        return None