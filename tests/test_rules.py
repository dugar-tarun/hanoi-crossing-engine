"""Tests for the pure rule predicates in ``hanoi.engine.rules``."""

from __future__ import annotations

import pytest

from conftest import make_state
from hanoi.engine import (
    GameConfig,
    build_two_player_config,
    disks_owned_by,
    goal_pole_of,
    hanoi_placement_legal,
    is_won_for,
)

# ----------------------------------------------------------------------------
# Ownership / goal lookups
# ----------------------------------------------------------------------------


def test_disks_owned_by_n3() -> None:
    cfg = build_two_player_config(3)
    assert disks_owned_by(cfg, "A") == frozenset({1, 3, 5})
    assert disks_owned_by(cfg, "B") == frozenset({2, 4, 6})


def test_goal_pole_of() -> None:
    cfg = build_two_player_config(3)
    assert goal_pole_of(cfg, "A") == "3a"
    assert goal_pole_of(cfg, "B") == "3b"


# ----------------------------------------------------------------------------
# Hanoi placement rule
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stack,disk,expected",
    [
        ((), 1, True),
        ((), 99, True),
        ((5,), 3, True),
        ((5, 3), 2, True),
        ((3,), 5, False),  # bigger on smaller
        ((3,), 3, False),  # equal not allowed
        ((5, 3, 1), 2, False),  # smaller-than-2 (1) is on top
    ],
)
def test_hanoi_placement_legal(stack: tuple[int, ...], disk: int, expected: bool) -> None:
    assert hanoi_placement_legal(stack, disk) is expected


# ----------------------------------------------------------------------------
# is_won_for: each clause exercised individually
# ----------------------------------------------------------------------------


def test_initial_state_is_not_won(cfg_n3: GameConfig) -> None:
    s = make_state(cfg_n3, poles={"1a": (5, 3, 1), "1b": (6, 4, 2)}, hands={})
    assert not is_won_for(s, "A")
    assert not is_won_for(s, "B")


def test_win_clause_hand_must_be_empty(cfg_n2: GameConfig) -> None:
    """All A disks parked on 3a, but A is still holding something -> not won."""
    s = make_state(
        cfg_n2,
        poles={"3a": (3, 1), "1b": (4, 2)},
        hands={"A": 99, "B": None},  # A holds a phantom disk; clause 1 fails.
    )
    assert not is_won_for(s, "A")


def test_win_clause_all_owned_disks_on_goal(cfg_n2: GameConfig) -> None:
    """Missing one A disk on 3a -> ownership clause fails."""
    # Disk 1 ended up parked on the shared pole, not on 3a.
    s = make_state(
        cfg_n2,
        poles={"3a": (3,), "2": (1,), "1b": (4, 2)},
        hands={"A": None, "B": None},
    )
    assert not is_won_for(s, "A")


def test_win_clause_no_owned_disk_elsewhere(cfg_n2: GameConfig) -> None:
    """A's owned disks all on 3a, but a duplicate copy parked elsewhere fails clause 3.

    (We can't legally produce duplicates, but the predicate still rejects.)
    """
    s = make_state(
        cfg_n2,
        # Imagine an extra A disk hiding on pole 2 — ownership-clause must reject.
        poles={"3a": (3, 1), "2": (3,), "1b": (4, 2)},
        hands={"A": None, "B": None},
    )
    assert not is_won_for(s, "A")


def test_win_clause_visible_non_goal_pole_must_be_empty(cfg_n2: GameConfig) -> None:
    """An opponent disk parked on the shared pole blocks A's win."""
    s = make_state(
        cfg_n2,
        poles={"3a": (3, 1), "2": (4,), "1b": (2,)},  # B parked disk 4 on 2.
        hands={"A": None, "B": None},
    )
    assert not is_won_for(s, "A")


def test_win_clause_a_disk_cannot_be_in_b_hand(cfg_n2: GameConfig) -> None:
    s = make_state(
        cfg_n2,
        poles={"3a": (3,), "1b": (4, 2)},
        hands={"A": None, "B": 1},  # B is holding A's disk — A is not won.
    )
    assert not is_won_for(s, "A")


def test_win_state_is_won(cfg_n2: GameConfig) -> None:
    """All four win clauses simultaneously satisfied."""
    s = make_state(
        cfg_n2,
        poles={"1a": (), "1b": (4, 2), "2": (), "3a": (3, 1), "3b": ()},
        hands={"A": None, "B": None},
    )
    assert is_won_for(s, "A")
    # B is not won — B's disks are still on 1b, not on 3b.
    assert not is_won_for(s, "B")


def test_trapping_does_not_block_owners_win(cfg_n2: GameConfig) -> None:
    """A may legally end the game with B disks interleaved into 3a; A still wins.

    See TRD §2: the win check is ownership-only on the goal pole. Disks in 3a
    that don't belong to A are simply ignored by clause 2 ("every owned disk
    on goal").
    """
    s = make_state(
        cfg_n2,
        # 3a stack bottom->top: B's disk 4, A's disk 3, A's disk 1.
        # A's owned disks {1, 3} are all on 3a; the foreign disk 4 is OK.
        poles={"1a": (), "1b": (), "2": (), "3a": (4, 3, 1), "3b": (2,)},
        hands={"A": None, "B": None},
    )
    assert is_won_for(s, "A")


def test_visible_pole_clause_only_applies_to_visible_poles(cfg_n3: GameConfig) -> None:
    """Disks on poles A can't see don't affect A's win — sanity check.

    Construct an absurd-but-legal-to-the-predicate state: B's private pole
    (1b/3b) has stuff on it, but A is still won because A only sees 1a/2/3a.
    """
    s = make_state(
        cfg_n3,
        poles={
            "1a": (),
            "1b": (),
            "2": (),
            "3a": (5, 3, 1),
            "3b": (6, 4, 2),  # B parked their disks on 3b — invisible to A.
        },
        hands={"A": None, "B": None},
    )
    assert is_won_for(s, "A")
