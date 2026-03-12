"""Bridge interfaces and adapters."""

from .base import Bridge
from .file_queue import FileQueueBridge
from .local_http import LocalHttpBridge


def create_bridge(settings):
    adapter = settings.bridge_adapter
    if adapter == "local_http":
        return LocalHttpBridge(settings)
    return FileQueueBridge(settings)


__all__ = ["Bridge", "FileQueueBridge", "LocalHttpBridge", "create_bridge"]
