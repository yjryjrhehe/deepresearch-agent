# src/backend/core/logging.py

import logging
import sys
from .config import settings

def setup_logging():
    """
    配置全局日志记录器。
    此函数应在应用启动时（例如 main.py）被调用一次。
    """
    
    # 获取 Pydantic settings.py 中定义的日志级别
    log_level = settings.log_level.upper()
    
    # 获取与 "log_level" 字符串匹配的日志级别对象
    numeric_level = getattr(logging, log_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"无效的日志级别: {settings.log_level}")

    # 定义一个新的、更好的日志格式
    # %(name)s 会显示 logger 的名字 (例如 "src.backend.services.agent_service")
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # (关键) 调用 basicConfig
    # stream=sys.stdout 确保日志输出到标准输出，这在 Docker 中是最佳实践
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        stream=sys.stdout 
    )
    
    # 打印一条日志，确认配置已生效
    logging.getLogger(__name__).info(f"日志系统已初始化，级别: {log_level}")