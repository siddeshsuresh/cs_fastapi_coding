# util.py
import time
import random
import logging
from functools import wraps
from typing import Callable, Iterable, Any, Tuple, Type

logger = logging.getLogger(__name__)

def backoff_retry(*dargs, **dkwargs):
    """
    Flexible decorator: supports
      @backoff_retry()
      @backoff_retry(exceptions=(Exception,), tries=5, base_delay=0.5, factor=2.0, jitter=0.25)
    """
    # Defaults
    exceptions: Tuple[Type[BaseException], ...] = dkwargs.pop("exceptions", (Exception,))
    tries: int = int(dkwargs.pop("tries", 5))
    base_delay: float = float(dkwargs.pop("base_delay", 0.5))
    factor: float = float(dkwargs.pop("factor", 2.0))
    jitter: float = float(dkwargs.pop("jitter", 0.25))

    def _decorate(func: Callable):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(1, tries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:  # only retries for the given exception types
                    if attempt == tries:
                        raise
                    sleep_for = max(0.0, delay + (jitter * (2 * random.random() - 1)))
                    logger.warning(
                        "Retryable error on %s attempt %s/%s: %s. Sleeping %.2fs",
                        func.__name__, attempt, tries, e, sleep_for
                    )
                    time.sleep(sleep_for)
                    delay *= factor
        return _wrapper

    # Used as @backoff_retry with no args
    if dargs and callable(dargs[0]) and not dkwargs:
        return _decorate(dargs[0])

    # Used as @backoff_retry(...)
    return _decorate
