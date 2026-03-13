# src/ui/history.py
"""History manager for sentence browsing functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import SentenceResult


class HistoryManager:
    """Manages sentence history with browsing support and automatic trimming.

    State Model:
        - LIVE mode (cursor == -1): User is viewing the latest content
        - BROWSE mode (cursor >= 0): User is browsing history

    Attributes:
        is_browsing: Whether currently browsing history.
        current: Content at current browse position, or latest in LIVE mode.
        latest: The most recently received sentence.
        can_go_prev: Whether can browse backwards.
        can_go_next: Whether can browse forwards.
        max_size: Maximum number of history records.
        count: Current number of history records.
        cursor_index: Current browse index for debugging, -1 for LIVE mode.
    """

    def __init__(self, max_size: int) -> None:
        """Initialize the history manager.

        Args:
            max_size: Maximum number of history records, must be >= 1.

        Raises:
            ValueError: If max_size < 1.
        """
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")
        self._max_size = max_size
        self._entries: list[SentenceResult] = []
        self._cursor: int = -1  # -1 = LIVE mode

    # ========== Properties ==========

    @property
    def is_browsing(self) -> bool:
        """Check if currently browsing history (not LIVE mode).

        Returns:
            True if in BROWSE mode, False if in LIVE mode or empty history.
        """
        return self._cursor >= 0 and len(self._entries) > 0

    @property
    def current(self) -> "SentenceResult | None":
        """Get content at current browse position.

        In LIVE mode, returns the latest content.
        In BROWSE mode, returns the history entry at cursor.
        Returns None if history is empty.

        Returns:
            The current SentenceResult or None if empty.
        """
        if not self._entries:
            return None
        if self._cursor == -1:
            return self._entries[-1]
        return self._entries[self._cursor]

    @property
    def latest(self) -> "SentenceResult | None":
        """Get the most recently received sentence.

        Returns:
            The latest SentenceResult or None if empty.
        """
        return self._entries[-1] if self._entries else None

    @property
    def can_go_prev(self) -> bool:
        """Check if can browse backwards to older content.

        Returns:
            True if there is older content to browse.
        """
        return len(self._entries) > 1 and (self._cursor == -1 or self._cursor > 0)

    @property
    def can_go_next(self) -> bool:
        """Check if can browse forwards to newer content.

        Returns:
            True if there is newer content to browse.
        """
        return self._cursor >= 0 and self._cursor < len(self._entries) - 1

    @property
    def max_size(self) -> int:
        """Get maximum number of history records.

        Returns:
            The maximum capacity.
        """
        return self._max_size

    @property
    def count(self) -> int:
        """Get current number of history records.

        Returns:
            The number of entries in history.
        """
        return len(self._entries)

    @property
    def cursor_index(self) -> int:
        """Get current browse index for debugging.

        Returns:
            Current cursor position, -1 for LIVE mode.
        """
        return self._cursor

    # ========== Operations ==========

    def add(self, result: "SentenceResult") -> None:
        """Add a new sentence to history.

        If history is full, automatically removes the oldest entry.
        Adding does not change browse mode (stays in BROWSE or LIVE).

        Args:
            result: The sentence result to add.
        """
        was_at_oldest = self._cursor == 0

        self._entries.append(result)
        if len(self._entries) > self._max_size:
            self._entries.pop(0)

            if self._cursor > 0:
                self._cursor -= 1
            elif was_at_oldest:
                # User was viewing the oldest entry which was removed.
                # Keep cursor at 0 to show what was previously the second oldest.
                # This provides continuity in browsing experience.
                pass  # cursor stays at 0

    def go_prev(self) -> bool:
        """Browse backwards to older content.

        Calling in LIVE mode enters BROWSE mode.

        Returns:
            True if successfully moved, False if already at oldest entry.
        """
        if not self.can_go_prev:
            return False

        if self._cursor == -1:
            # Enter BROWSE mode from LIVE mode
            self._cursor = len(self._entries) - 2
        else:
            self._cursor -= 1

        return True

    def go_next(self) -> bool:
        """Browse forwards to newer content.

        If reaching the latest entry, returns False and enters LIVE mode.

        Returns:
            True if successfully moved and still in BROWSE mode,
            False if reached end and entered LIVE mode.
        """
        if not self.can_go_next:
            return False

        self._cursor += 1
        if self._cursor >= len(self._entries) - 1:
            # Reached latest, return to LIVE mode
            self._cursor = -1
            return False

        return True

    def go_live(self) -> None:
        """Directly return to LIVE mode to view latest content."""
        self._cursor = -1

    def resize(self, new_max: int) -> None:
        """Resize maximum capacity.

        If new capacity is smaller than current history count,
        automatically removes oldest entries. If currently browsing
        an entry that will be removed, returns to LIVE mode.

        Args:
            new_max: New maximum capacity, must be >= 1.

        Raises:
            ValueError: If new_max < 1.
        """
        if new_max < 1:
            raise ValueError(f"new_max must be >= 1, got {new_max}")

        to_remove = len(self._entries) - new_max
        if to_remove <= 0:
            self._max_size = new_max
            return

        # Critical fix: check if cursor points to an entry being removed
        if self._cursor >= 0 and self._cursor < to_remove:
            # Cursor points to an entry that will be removed, return to LIVE mode
            self._cursor = -1
        elif self._cursor > 0:
            # Cursor is in retained range, adjust index
            self._cursor -= to_remove

        # Remove oldest entries
        for _ in range(to_remove):
            self._entries.pop(0)

        self._max_size = new_max

    def clear(self) -> None:
        """Clear all history records."""
        self._entries.clear()
        self._cursor = -1

    # ========== Special Methods ==========

    def __len__(self) -> int:
        return len(self._entries)

    def __bool__(self) -> bool:
        return len(self._entries) > 0

    def __repr__(self) -> str:
        mode = "BROWSE" if self.is_browsing else "LIVE"
        return (
            f"HistoryManager(count={len(self._entries)}, "
            f"max={self._max_size}, mode={mode}, cursor={self._cursor})"
        )
