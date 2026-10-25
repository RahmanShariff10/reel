"""Centralised logging setup for Reel.

Usage::

    from reel.common.logging import get_logger

    log = get_logger(__name__)
    log.info("Starting stage %s", stage_name)

Call :func:`setup_logging` once at process start (the worker and the API
server each call it).  :func:`get_logger` works without calling
``setup_logging`` first — it just returns a stdlib logger — but the
output format won't be configured until ``setup_logging`` runs.
"""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level: int | str = logging.INFO) -> None:
    """Configure the root ``reel`` logger.

    Safe to call more than once — subsequent calls are no-ops.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger("reel")
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)

    # Prevent messages from propagating to the root logger and being
    # printed twice when another library has also configured root.
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``reel`` namespace.

    If *name* already starts with ``reel.`` it is used as-is; otherwise
    ``reel.`` is prepended so all Reel loggers share one hierarchy.
    """
    if not name.startswith("reel."):
        name = f"reel.{name}"
    return logging.getLogger(name)
