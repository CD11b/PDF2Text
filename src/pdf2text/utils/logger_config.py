import logging
import sys
from logging import Logger


def setup_logging(log_file: str = "./tests/pdf2text.log", log_level: str = "INFO") -> Logger | None:
    """Configure logging for the application."""

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return None

    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO),
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout),  # Log to console
                                  logging.FileHandler(log_file, mode='w', encoding='utf-8')  # Log to file
                        ]
                        )

    logger = logging.getLogger(__name__)
    return logger