"""
구조화된 로깅 설정
"""
import logging
import sys
from rich.logging import RichHandler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            show_path=False,
        )
        handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%H:%M:%S]"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
