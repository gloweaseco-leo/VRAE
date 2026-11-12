"""Private read-only Operator Console interface; real runtime integration is unavailable."""
from .contracts import ConsoleError
from .service import ConsoleService

__all__ = ['ConsoleError', 'ConsoleService']
