from dataclasses import dataclass
from enum import Enum
import logging

class Action(Enum):
    """Actions that can be taken on a line group."""

    COLLECT = (True, logging.DEBUG, "Collected")
    SKIP = (False, logging.INFO, "Skipped")
    UNHANDLED = (False, logging.WARNING, "Unhandled")

    def __init__(self, should_collect: bool, log_level: int, label: str):
        self._should_collect = should_collect
        self._log_level = log_level
        self._label = label

    @property
    def should_collect(self) -> bool:
        return self._should_collect

    @property
    def log_level(self) -> int:
        return self._log_level

    @property
    def action_label(self) -> str:
        return self._label

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