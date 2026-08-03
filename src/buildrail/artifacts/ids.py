"""Injectable clock and id-generator for deterministic artifact run ids in tests."""

import secrets
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Supplies the current UTC time."""

    def utcnow(self) -> datetime:
        """Return the current UTC time."""
        ...


class IdGenerator(Protocol):
    """Supplies short, unique id suffixes."""

    def next_id(self) -> str:
        """Return a new id suffix."""
        ...


class SystemClock:
    """The real system clock."""

    def utcnow(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)


class SystemIdGenerator:
    """Generates random hex suffixes using the OS's secure randomness source."""

    def next_id(self) -> str:
        """Return a new random hex suffix."""
        return secrets.token_hex(3)
