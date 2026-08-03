"""Deterministic Clock and IdGenerator test doubles for artifact run ids."""

from datetime import datetime


class FixedClock:
    """A Clock that always returns the same fixed UTC datetime."""

    def __init__(self, value: datetime) -> None:
        self._value = value

    def utcnow(self) -> datetime:
        """Return the fixed datetime this clock was constructed with."""
        return self._value


class FixedIdGenerator:
    """An IdGenerator that always returns the same fixed suffix."""

    def __init__(self, value: str) -> None:
        self._value = value

    def next_id(self) -> str:
        """Return the fixed suffix this generator was constructed with."""
        return self._value
