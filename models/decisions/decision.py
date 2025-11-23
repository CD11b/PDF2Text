from dataclasses import dataclass
from enum import Enum, auto

class Action(Enum):
    """Actions that can be taken on a line group."""
    COLLECT = auto()
    SKIP = auto()
    UNHANDLED = auto()

@dataclass(frozen=True, slots=True)
class Decision:
    """
    Immutable decision result from a handler.

    Contains the action to take and a human-readable reason for logging/debugging.
    """
    action: Action
    reason: str
    handler_name: str

    @classmethod
    def collect(cls, reason: str, handler: str) -> 'Decision':
        return cls(Action.COLLECT, reason, handler)

    @classmethod
    def skip(cls, reason: str, handler: str) -> 'Decision':
        return cls(Action.SKIP, reason, handler)

    @classmethod
    def unhandled(cls, reason: str, handler: str) -> 'Decision':
        return cls(Action.UNHANDLED, reason, handler)