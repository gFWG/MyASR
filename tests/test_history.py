# tests/test_history.py
"""Unit tests for HistoryManager."""

from datetime import datetime

import pytest

from src.db.models import AnalysisResult, SentenceResult
from src.ui.history import HistoryManager


def _make_result(text: str) -> SentenceResult:
    """Create a minimal SentenceResult for testing."""
    return SentenceResult(
        japanese_text=text,
        analysis=AnalysisResult(tokens=[], vocab_hits=[], grammar_hits=[]),
        created_at=datetime.now(),
    )


class TestHistoryManagerInit:
    """Tests for HistoryManager initialization."""

    def test_init_with_valid_max_size(self) -> None:
        """HistoryManager initializes with valid max_size."""
        history = HistoryManager(10)
        assert history.max_size == 10
        assert history.count == 0
        assert history.cursor_index == -1
        assert not history.is_browsing

    def test_init_with_max_size_one(self) -> None:
        """HistoryManager accepts max_size=1."""
        history = HistoryManager(1)
        assert history.max_size == 1

    def test_init_with_invalid_max_size_zero(self) -> None:
        """HistoryManager raises ValueError for max_size=0."""
        with pytest.raises(ValueError, match="max_size must be >= 1"):
            HistoryManager(0)

    def test_init_with_invalid_max_size_negative(self) -> None:
        """HistoryManager raises ValueError for negative max_size."""
        with pytest.raises(ValueError, match="max_size must be >= 1"):
            HistoryManager(-5)


class TestHistoryManagerEmpty:
    """Tests for empty history behavior."""

    @pytest.fixture
    def empty_history(self) -> HistoryManager:
        """Return an empty HistoryManager."""
        return HistoryManager(5)

    def test_empty_is_browsing(self, empty_history: HistoryManager) -> None:
        """Empty history is not browsing."""
        assert not empty_history.is_browsing

    def test_empty_current(self, empty_history: HistoryManager) -> None:
        """Empty history returns None for current."""
        assert empty_history.current is None

    def test_empty_latest(self, empty_history: HistoryManager) -> None:
        """Empty history returns None for latest."""
        assert empty_history.latest is None

    def test_empty_can_go_prev(self, empty_history: HistoryManager) -> None:
        """Empty history cannot go prev."""
        assert not empty_history.can_go_prev

    def test_empty_can_go_next(self, empty_history: HistoryManager) -> None:
        """Empty history cannot go next."""
        assert not empty_history.can_go_next

    def test_empty_go_prev(self, empty_history: HistoryManager) -> None:
        """Empty history go_prev returns False."""
        assert not empty_history.go_prev()

    def test_empty_go_next(self, empty_history: HistoryManager) -> None:
        """Empty history go_next returns False."""
        assert not empty_history.go_next()

    def test_empty_len(self, empty_history: HistoryManager) -> None:
        """Empty history len is 0."""
        assert len(empty_history) == 0

    def test_empty_bool(self, empty_history: HistoryManager) -> None:
        """Empty history is falsy."""
        assert not empty_history


class TestHistoryManagerAdd:
    """Tests for add operation."""

    def test_add_first_record(self) -> None:
        """Adding first record creates history with LIVE mode."""
        history = HistoryManager(5)
        result = _make_result("テスト")

        history.add(result)

        assert history.count == 1
        assert history.current == result
        assert history.latest == result
        assert not history.is_browsing

    def test_add_multiple_records(self) -> None:
        """Adding multiple records builds history."""
        history = HistoryManager(5)
        results = [_make_result(f"text{i}") for i in range(3)]

        for r in results:
            history.add(r)

        assert history.count == 3
        assert history.latest == results[2]
        assert not history.is_browsing

    def test_add_auto_trim(self) -> None:
        """Adding beyond max_size auto-trims oldest."""
        history = HistoryManager(3)
        results = [_make_result(f"text{i}") for i in range(5)]

        for r in results:
            history.add(r)

        assert history.count == 3
        assert history.latest == results[4]
        # Oldest should be removed (text0, text1 removed)
        assert history.current == results[4]

    def test_add_does_not_change_browse_mode(self) -> None:
        """Adding while browsing stays in BROWSE mode."""
        history = HistoryManager(5)
        results = [_make_result(f"text{i}") for i in range(3)]

        for r in results:
            history.add(r)

        # Enter browse mode
        history.go_prev()
        assert history.is_browsing

        # Add new result while browsing
        new_result = _make_result("new")
        history.add(new_result)

        # Should stay in browse mode
        assert history.is_browsing
        # Latest should be updated
        assert history.latest == new_result

    def test_add_trim_while_browsing_oldest(self) -> None:
        """Trimming oldest while browsing it keeps continuity."""
        history = HistoryManager(3)
        results = [_make_result(f"text{i}") for i in range(3)]

        for r in results:
            history.add(r)

        # Browse to oldest (cursor=0)
        history.go_prev()  # cursor=1
        history.go_prev()  # cursor=0
        assert history.cursor_index == 0
        assert history.current == results[0]

        # Add two more to trim oldest (text0)
        history.add(_make_result("text3"))  # Removes text0, cursor stays at 0 -> now text1
        assert history.current == results[1]
        history.add(_make_result("text4"))  # Removes text1, cursor stays at 0 -> now text2

        # Cursor should stay at 0, now pointing to text2
        assert history.cursor_index == 0
        assert history.current == results[2]


class TestHistoryManagerBrowse:
    """Tests for browsing operations."""

    @pytest.fixture
    def history(self) -> HistoryManager:
        """Return a history with 5 entries in LIVE mode."""
        h = HistoryManager(10)
        for i in range(5):
            h.add(_make_result(f"text{i}"))
        return h

    def test_go_prev_enters_browse_mode(self, history: HistoryManager) -> None:
        """go_prev from LIVE mode enters BROWSE mode."""
        assert not history.is_browsing

        result = history.go_prev()

        assert result is True
        assert history.is_browsing
        assert history.cursor_index == 3  # Second to last

    def test_go_prev_moves_backward(self, history: HistoryManager) -> None:
        """go_prev in BROWSE mode moves cursor backward."""
        history.go_prev()  # cursor=3
        history.go_prev()  # cursor=2

        assert history.cursor_index == 2

    def test_go_prev_at_oldest_returns_false(self, history: HistoryManager) -> None:
        """go_prev at oldest entry returns False."""
        # Navigate to oldest
        history.go_prev()  # cursor=3
        history.go_prev()  # cursor=2
        history.go_prev()  # cursor=1
        history.go_prev()  # cursor=0

        assert history.cursor_index == 0
        assert not history.can_go_prev
        assert not history.go_prev()
        assert history.cursor_index == 0

    def test_go_next_moves_forward(self, history: HistoryManager) -> None:
        """go_next in BROWSE mode moves cursor forward."""
        history.go_prev()  # cursor=3
        history.go_prev()  # cursor=2

        history.go_next()

        assert history.cursor_index == 3

    def test_go_next_enters_live_mode(self, history: HistoryManager) -> None:
        """go_next at latest entry enters LIVE mode."""
        history.go_prev()  # cursor=3

        result = history.go_next()

        assert result is False  # Returns False when entering LIVE
        assert not history.is_browsing
        assert history.cursor_index == -1

    def test_go_next_in_live_mode_returns_false(self, history: HistoryManager) -> None:
        """go_next in LIVE mode returns False."""
        assert not history.is_browsing
        assert not history.can_go_next
        assert not history.go_next()

    def test_go_live_returns_to_live_mode(self, history: HistoryManager) -> None:
        """go_live directly returns to LIVE mode."""
        history.go_prev()
        history.go_prev()
        assert history.is_browsing

        history.go_live()

        assert not history.is_browsing
        assert history.cursor_index == -1

    def test_can_go_prev_with_single_entry(self) -> None:
        """can_go_prev is False with single entry."""
        history = HistoryManager(5)
        history.add(_make_result("only"))

        assert not history.can_go_prev
        assert not history.go_prev()

    def test_browse_current_points_to_correct_entry(self, history: HistoryManager) -> None:
        """current returns entry at cursor position."""
        history.go_prev()  # cursor=3, text3
        assert history.current is not None
        assert history.current.japanese_text == "text3"

        history.go_prev()  # cursor=2, text2
        assert history.current is not None
        assert history.current.japanese_text == "text2"


class TestHistoryManagerResize:
    """Tests for resize operation."""

    def test_resize_increase_capacity(self) -> None:
        """Resize can increase capacity."""
        history = HistoryManager(3)
        for i in range(3):
            history.add(_make_result(f"text{i}"))

        history.resize(5)

        assert history.max_size == 5
        assert history.count == 3

    def test_resize_decrease_capacity_trims(self) -> None:
        """Resize decreasing capacity trims oldest entries."""
        history = HistoryManager(5)
        for i in range(5):
            history.add(_make_result(f"text{i}"))

        history.resize(3)

        assert history.max_size == 3
        assert history.count == 3
        # Should have text2, text3, text4
        assert history.latest is not None
        assert history.latest.japanese_text == "text4"

    def test_resize_while_browsing_reset_to_live(self) -> None:
        """Resize while browsing removed entry returns to LIVE mode."""
        history = HistoryManager(10)
        for i in range(10):
            history.add(_make_result(f"text{i}"))

        # Browse to cursor=2 (text2)
        history.go_prev()  # cursor=8
        history.go_prev()  # cursor=7
        history.go_prev()  # cursor=6
        history.go_prev()  # cursor=5
        history.go_prev()  # cursor=4
        history.go_prev()  # cursor=3
        history.go_prev()  # cursor=2

        assert history.cursor_index == 2

        # Resize to 3 - cursor=2 will be removed
        history.resize(3)

        # Should return to LIVE mode
        assert not history.is_browsing
        assert history.cursor_index == -1

    def test_resize_while_browsing_adjusts_cursor(self) -> None:
        """Resize while browsing retained entry adjusts cursor."""
        history = HistoryManager(10)
        for i in range(10):
            history.add(_make_result(f"text{i}"))

        # Browse to cursor=5 (text5)
        history.go_prev()  # cursor=8
        history.go_prev()  # cursor=7
        history.go_prev()  # cursor=6
        history.go_prev()  # cursor=5

        assert history.cursor_index == 5

        # Resize to 5 - remove 5 entries (0-4), cursor should become 0
        history.resize(5)

        assert history.is_browsing
        # cursor = 5 - 5 = 0
        assert history.cursor_index == 0

    def test_resize_to_one(self) -> None:
        """Resize to 1 leaves only latest entry."""
        history = HistoryManager(10)
        for i in range(5):
            history.add(_make_result(f"text{i}"))

        history.resize(1)

        assert history.max_size == 1
        assert history.count == 1
        assert history.latest is not None
        assert history.latest.japanese_text == "text4"

    def test_resize_invalid_raises(self) -> None:
        """Resize with invalid value raises ValueError."""
        history = HistoryManager(5)

        with pytest.raises(ValueError, match="new_max must be >= 1"):
            history.resize(0)

        with pytest.raises(ValueError, match="new_max must be >= 1"):
            history.resize(-1)


class TestHistoryManagerClear:
    """Tests for clear operation."""

    def test_clear_empty_history(self) -> None:
        """Clear on empty history is no-op."""
        history = HistoryManager(5)
        history.clear()

        assert history.count == 0
        assert not history.is_browsing

    def test_clear_non_empty_history(self) -> None:
        """Clear removes all entries and returns to LIVE mode."""
        history = HistoryManager(5)
        for i in range(3):
            history.add(_make_result(f"text{i}"))

        history.go_prev()
        assert history.is_browsing

        history.clear()

        assert history.count == 0
        assert not history.is_browsing
        assert history.cursor_index == -1
        assert history.current is None
        assert history.latest is None


class TestHistoryManagerSpecialMethods:
    """Tests for special methods."""

    def test_len(self) -> None:
        """__len__ returns count."""
        history = HistoryManager(5)
        assert len(history) == 0

        history.add(_make_result("test"))
        assert len(history) == 1

    def test_bool(self) -> None:
        """__bool__ returns True if non-empty."""
        history = HistoryManager(5)
        assert not history

        history.add(_make_result("test"))
        assert history

    def test_repr(self) -> None:
        """__repr__ shows useful debug info."""
        history = HistoryManager(5)
        assert "LIVE" in repr(history)
        assert "count=0" in repr(history)

        history.add(_make_result("test1"))
        history.add(_make_result("test2"))
        history.go_prev()  # Need 2+ entries to enter BROWSE mode
        assert "BROWSE" in repr(history)


class TestHistoryManagerEdgeCases:
    """Tests for edge cases from design document."""

    def test_consecutive_add_in_browse_mode(self) -> None:
        """Consecutive adds in BROWSE mode shift the window."""
        history = HistoryManager(3)
        results = [_make_result(f"text{i}") for i in range(3)]

        for r in results:
            history.add(r)

        # Browse to oldest
        history.go_prev()  # cursor=1
        history.go_prev()  # cursor=0
        assert history.current == results[0]

        # Add more - the window shifts
        new1 = _make_result("text3")
        history.add(new1)  # Removes text0, cursor stays at 0
        assert history.current == results[1]  # Now at text1

        new2 = _make_result("text4")
        history.add(new2)  # Removes text1, cursor stays at 0
        assert history.current == results[2]  # Now at text2

    def test_go_prev_then_add_updates_latest(self) -> None:
        """After go_prev, add updates latest while keeping browse position."""
        history = HistoryManager(5)
        results = [_make_result(f"text{i}") for i in range(3)]

        for r in results:
            history.add(r)

        history.go_prev()  # cursor=1, browsing text1
        assert history.is_browsing
        assert history.current == results[1]
        assert history.latest == results[2]

        new = _make_result("text3")
        history.add(new)

        # Current should still be text1
        assert history.current == results[1]
        # Latest should be updated
        assert history.latest == new

    def test_single_entry_cannot_browse(self) -> None:
        """Single entry history cannot enter BROWSE mode."""
        history = HistoryManager(5)
        history.add(_make_result("only"))

        assert not history.can_go_prev
        assert not history.go_prev()
        assert not history.is_browsing
