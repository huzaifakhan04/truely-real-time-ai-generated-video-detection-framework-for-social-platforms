import logging

from config import AUTH_LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: The name of the logger

    Returns:
        A logger with the given name

    Raises:
        None
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        level_name = (AUTH_LOG_LEVEL or "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logger.setLevel(level)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger


