"""Bridge interfaces and adapters."""

from .base import Bridge
from .file_queue import FileQueueBridge

__all__ = ["Bridge", "FileQueueBridge"]

