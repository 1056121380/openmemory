"""OpenMemory Server Module.

Provides REST APIs, Web Review Console, and background digest workers.
"""

from .app import app, start_server

__all__ = ["app", "start_server"]
