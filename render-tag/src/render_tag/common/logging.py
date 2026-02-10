import logging
import sys


def setup_logging(level: int = logging.INFO):
    """Sets up standard logging configuration for the project."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Gets a logger instance for a given name."""
    return logging.getLogger(name)
