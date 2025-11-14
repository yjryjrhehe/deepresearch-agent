import time
import logging
from pathlib import Path

from ...src.backend.domain.models import DocumentSource
from ...src.backend.infrastructure.parsing.parser import DoclingParser
from ...src.backend.core.logging import setup_logging 


# === 日志配置 ===
setup_logging()
log = logging.getLogger(__name__)

if __name__ == "__main__":
    
    log.info("--- 开始 DoclingVLMParser 测试 ---")
    log.warning("确保 .env 文件已在正确位置并包含所有 DOCLING_... 变量。")
    start = time.time()
    
    # 1. 初始化解析器
    # (这将从 .env 加载配置)
    try:
        parser = DoclingParser()
    except Exception as e:
        log.error(f"无法初始化 DoclingVLMParser (请检查 .env 文件和配置): {e}", exc_info=True)
        exit(1)

    # 2. 定义输入和输出
    # input_doc_path: Path = Path(r".\test\test.pdf")
    input_doc_path: Path = Path(r"E:\02open-project\deepresearch-agent\test\parser_test\test.pdf")
    output_md_path: Path = Path(r"E:\02open-project\deepresearch-agent\test\parser_test\test.md")
    
    # 3. 创建 DocumentSource
    doc_source = DocumentSource(file_path=input_doc_path)
    
    # 4. 执行解析 (调用 parse)
    try:
        log.info(f"开始解析 {doc_source.file_path}...")
        md_string = parser.parse(doc_source)
        
        # 5. 将返回的字符串保存到文件
        with open(output_md_path, 'w', encoding='utf-8') as f:
            f.write(md_string)
            
        log.info(f"成功！Markdown 内容已保存到: {output_md_path}")
        
    except FileNotFoundError:
        log.error(f"测试失败: 输入文件 {input_doc_path} 未找到。")
    except Exception as e:
        log.error(f"测试期间发生错误: {e}", exc_info=True)

    end = time.time()
    log.info(f"总转换时间为：{end-start:.6f} 秒。")