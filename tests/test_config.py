"""Tests for ``GameConfig`` invariants and ``build_two_player_config``."""

from __future__ import annotations

import pytest

from hanoi.engine import (
    ConfigError,
    GameConfig,
    PoleSpec,
    build_two_player_config,
)

# ----------------------------------------------------------------------------
# build_two_player_config
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("n", [1, 2, 3, 5, 10])
def test_build_two_player_disk_partition(n: int) -> None:
    cfg = build_two_player_config(n)
    a = sorted(d for d, owner in cfg.disk_owner.items() if owner == "A")
    b = sorted(d for d, owner in cfg.disk_owner.items() if owner == "B")
    assert a == [2 * i - 1 for i in range(1, n + 1)]
    assert b == [2 * i for i in range(1, n + 1)]


def test_build_two_player_default_max_turns() -> None:
    assert build_two_player_config(3).max_turns == 1000


def test_build_two_player_rejects_zero_disks() -> None:
    with pytest.raises(ConfigError):
        build_two_player_config(0)


def test_build_two_player_rejects_negative_max_turns() -> None:
    with pytest.raises(ConfigError):
        build_two_player_config(2, max_turns=0)
    with pytest.raises(ConfigError):
        build_two_player_config(2, max_turns=-5)


def test_build_two_player_initial_stacks_top_disk_is_smallest() -> None:
    cfg = build_two_player_config(4)
    # Stacks are bottom..top; the rightmost element is the top disk.
    assert cfg.initial_stacks["1a"][-1] == 1
    assert cfg.initial_stacks["1b"][-1] == 2


# ----------------------------------------------------------------------------
# GameConfig invariants enforced at __post_init__
# ----------------------------------------------------------------------------


def _basic_kwargs() -> dict:
    return dict(
        players=("A", "B"),
        poles=(
            PoleSpec("1a", frozenset({"A"}), frozenset()),
            PoleSpec("1b", frozenset({"B"}), frozenset()),
            PoleSpec("3a", frozenset({"A"}), frozenset({"A"})),
            PoleSpec("3b", frozenset({"B"}), frozenset({"B"})),
        ),
        initial_stacks={"1a": (1,), "1b": (2,), "3a": (), "3b": ()},
        disk_owner={1: "A", 2: "B"},
        max_turns=10,
    )


def test_config_rejects_duplicate_players() -> None:
    kw = _basic_kwargs()
    kw["players"] = ("A", "A")
    with pytest.raises(ConfigError):
        GameConfig(**kw)


def test_config_rejects_duplicate_pole_ids() -> None:
    kw = _basic_kwargs()
    kw["poles"] = (
        PoleSpec("X", frozenset({"A"}), frozenset({"A"})),
        PoleSpec("X", frozenset({"B"}), frozenset({"B"})),
    )
    kw["initial_stacks"] = {"X": ()}
    kw["disk_owner"] = {}
    with pytest.raises(ConfigError):
        GameConfig(**kw)


def test_config_rejects_initial_stacks_mismatch() -> None:
    kw = _basic_kwargs()
    kw["initial_stacks"] = {"1a": (1,), "1b": (2,)}  # missing 3a/3b.
    with pytest.raises(ConfigError):
        GameConfig(**kw)


def test_config_rejects_duplicate_disks_across_stacks() -> None:
    kw = _basic_kwargs()
    kw["initial_stacks"] = {"1a": (1,), "1b": (1,), "3a": (), "3b": ()}
    kw["disk_owner"] = {1: "A"}
    with pytest.raises(ConfigError):
        GameConfig(**kw)


def test_config_rejects_disk_owner_disagreeing_with_stacks() -> None:
    kw = _basic_kwargs()
    kw["disk_owner"] = {1: "A"}  # disk 2 placed but unowned.
    with pytest.raises(ConfigError):
        GameConfig(**kw)


def test_config_rejects_unknown_disk_owner() -> None:
    kw = _basic_kwargs()
    kw["disk_owner"] = {1: "A", 2: "Z"}
    with pytest.raises(ConfigError):
        GameConfig(**kw)


def test_config_rejects_player_without_goal_pole() -> None:
    kw = _basic_kwargs()
    kw["poles"] = (
        PoleSpec("1a", frozenset({"A"}), frozenset()),
        PoleSpec("1b", frozenset({"B"}), frozenset()),
        PoleSpec("3a", frozenset({"A"}), frozenset()),
        PoleSpec("3b", frozenset({"B"}), frozenset({"B"})),  # only B has a goal pole.
    )
    with pytest.raises(ConfigError):
        GameConfig(**kw)


def test_config_rejects_player_with_two_goal_poles() -> None:
    kw = _basic_kwargs()
    kw["poles"] = (
        PoleSpec("1a", frozenset({"A"}), frozenset({"A"})),
        PoleSpec("1b", frozenset({"B"}), frozenset()),
        PoleSpec("3a", frozenset({"A"}), frozenset({"A"})),
        PoleSpec("3b", frozenset({"B"}), frozenset({"B"})),
    )
    with pytest.raises(ConfigError):
        GameConfig(**kw)


def test_config_rejects_pole_visible_to_unknown_player() -> None:
    kw = _basic_kwargs()
    kw["poles"] = (
        PoleSpec("1a", frozenset({"A", "Z"}), frozenset()),
        PoleSpec("1b", frozenset({"B"}), frozenset()),
        PoleSpec("3a", frozenset({"A"}), frozenset({"A"})),
        PoleSpec("3b", frozenset({"B"}), frozenset({"B"})),
    )
    with pytest.raises(ConfigError):
        GameConfig(**kw)


def test_config_rejects_pole_with_empty_visibility() -> None:
    kw = _basic_kwargs()
    kw["poles"] = (
        PoleSpec("1a", frozenset(), frozenset()),
        PoleSpec("1b", frozenset({"B"}), frozenset()),
        PoleSpec("3a", frozenset({"A"}), frozenset({"A"})),
        PoleSpec("3b", frozenset({"B"}), frozenset({"B"})),
    )
    with pytest.raises(ConfigError):
        GameConfig(**kw)
