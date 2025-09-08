
import time
import logging
from typing import Callable, Type, Any, Iterable, Tuple

logger = logging.getLogger(__name__)

def backoff_retry(func: Callable, exceptions: Tuple[Type[BaseException], ...], *, tries: int = 5, base_delay: float = 0.5, factor: float = 2.0, jitter: float = 0.25):
    """
    Simple exponential backoff decorator-like helper.
    """
    def wrapper(*args, **kwargs):
        delay = base_delay
        for attempt in range(1, tries + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if attempt == tries:
                    raise
                sleep_for = delay + (jitter * (2*__import__("random").random()-1))
                logger.warning("Retryable error on %s attempt %s/%s: %s. Sleeping %.2fs", func.__name__, attempt, tries, e, sleep_for)
                time.sleep(sleep_for)
                delay *= factor
    return wrapper

def chunks(iterable: Iterable[Any], size: int):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
