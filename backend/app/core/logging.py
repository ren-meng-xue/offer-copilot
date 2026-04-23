import logging
import sys

from backend.app.core.config import get_settings


def setup_logging() -> None:
    """统一初始化应用日志，避免各模块重复配置 root logger。"""

    settings = get_settings()
    root_logger = logging.getLogger()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root_logger.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
    else:
        for handler in root_logger.handlers:
            handler.setLevel(log_level)
            handler.setFormatter(formatter)

    root_logger.info("日志系统初始化完成")
