"""Game configuration: ``PoleSpec``, ``GameConfig``, and the 2-player builder.

This is the only module that knows the concrete board layout for two players
(pole ids ``"1a" / "1b" / "2" / "3a" / "3b"``, players ``"A" / "B"``). The
engine itself reads only the abstract ``GameConfig``, so an N-player extension
is purely additive — add a new builder; nothing else needs to change.

Construction is the only place in the engine that may raise after a ``GameConfig``
is built; every other engine function is total. We therefore validate every
invariant up-front in ``__post_init__`` and raise ``ConfigError`` on violation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

PlayerId = str
PoleId = str


class ConfigError(ValueError):
    """Raised when a ``GameConfig`` (or its inputs) violates the invariants."""


@dataclass(frozen=True, slots=True)
class PoleSpec:
    """Static description of a single pole.

    Attributes:
        id:         Unique pole identifier.
        visible_to: Set of players who can see and act on this pole.
        goal_for:   Set of players for whom this pole is their winning destination.
    """

    id: PoleId
    visible_to: frozenset[PlayerId]
    goal_for: frozenset[PlayerId]


@dataclass(frozen=True, slots=True)
class GameConfig:
    """Immutable static description of the entire game.

    ``initial_stacks`` lists each pole's disks bottom-to-top (so index 0 is the
    bottom and ``[-1]`` is the top of the stack — the disk that gets lifted
    first). ``disk_owner`` is the canonical map ``disk_size -> player``.
    """

    players: tuple[PlayerId, ...]
    poles: tuple[PoleSpec, ...]
    initial_stacks: Mapping[PoleId, tuple[int, ...]]
    disk_owner: Mapping[int, PlayerId]
    max_turns: int

    # Cached, computed once in __post_init__ so engine hot paths don't re-scan.
    _pole_index: Mapping[PoleId, PoleSpec] = field(
        init=False, repr=False, compare=False
    )
    _goal_pole: Mapping[PlayerId, PoleId] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        # 1. Players are non-empty and unique.
        if len(self.players) < 1:
            raise ConfigError("config.players must be non-empty")
        if len(set(self.players)) != len(self.players):
            raise ConfigError("config.players contains duplicates")

        # 2. Poles are non-empty and have unique ids.
        if len(self.poles) < 1:
            raise ConfigError("config.poles must be non-empty")
        pole_ids = [p.id for p in self.poles]
        if len(set(pole_ids)) != len(pole_ids):
            raise ConfigError("config.poles contains duplicate ids")

        pole_index = {p.id: p for p in self.poles}
        pole_id_set = set(pole_ids)
        player_set = set(self.players)

        # 3. initial_stacks keys exactly match the pole ids.
        if set(self.initial_stacks.keys()) != pole_id_set:
            missing = pole_id_set - self.initial_stacks.keys()
            extra = self.initial_stacks.keys() - pole_id_set
            raise ConfigError(
                f"initial_stacks keys must equal pole ids "
                f"(missing={sorted(missing)}, extra={sorted(extra)})"
            )

        # 4. The placed disks across all stacks form a partition of disk_owner's domain.
        seen_disks: set[int] = set()
        for pid, stack in self.initial_stacks.items():
            for d in stack:
                if d in seen_disks:
                    raise ConfigError(
                        f"disk {d} appears in multiple stacks"
                    )
                seen_disks.add(d)
        if seen_disks != set(self.disk_owner.keys()):
            raise ConfigError(
                "set of placed disks must equal disk_owner.keys() "
                f"(placed={sorted(seen_disks)}, owned={sorted(self.disk_owner)})"
            )

        # 5. Every disk_owner value is a known player.
        for d, owner in self.disk_owner.items():
            if owner not in player_set:
                raise ConfigError(
                    f"disk {d} owned by unknown player {owner!r}"
                )

        # 6. Every player has exactly one goal pole.
        goal_for_player: dict[PlayerId, PoleId] = {}
        for spec in self.poles:
            for p in spec.goal_for:
                if p not in player_set:
                    raise ConfigError(
                        f"pole {spec.id!r} declares goal for unknown player {p!r}"
                    )
                if p in goal_for_player:
                    raise ConfigError(
                        f"player {p!r} has multiple goal poles "
                        f"({goal_for_player[p]!r} and {spec.id!r})"
                    )
                goal_for_player[p] = spec.id
        missing_goals = player_set - goal_for_player.keys()
        if missing_goals:
            raise ConfigError(
                f"players without a goal pole: {sorted(missing_goals)}"
            )

        # 7. visible_to is a non-empty subset of players for every pole.
        for spec in self.poles:
            if not spec.visible_to:
                raise ConfigError(
                    f"pole {spec.id!r} has empty visible_to"
                )
            unknown = spec.visible_to - player_set
            if unknown:
                raise ConfigError(
                    f"pole {spec.id!r} visible_to references unknown players "
                    f"{sorted(unknown)}"
                )

        # 8. max_turns positive.
        if self.max_turns <= 0:
            raise ConfigError(f"max_turns must be > 0, got {self.max_turns}")

        # Freeze the cached lookups behind read-only proxies. Using
        # object.__setattr__ because the dataclass is frozen.
        object.__setattr__(self, "_pole_index", MappingProxyType(pole_index))
        object.__setattr__(
            self, "_goal_pole", MappingProxyType(goal_for_player)
        )
        # Defensive copies for input mappings, also wrapped read-only.
        object.__setattr__(
            self,
            "initial_stacks",
            MappingProxyType({k: tuple(v) for k, v in self.initial_stacks.items()}),
        )
        object.__setattr__(
            self, "disk_owner", MappingProxyType(dict(self.disk_owner))
        )

    def pole(self, pole_id: PoleId) -> PoleSpec:
        return self._pole_index[pole_id]

    def goal_pole_of(self, player: PlayerId) -> PoleId:
        return self._goal_pole[player]


# ----------------------------------------------------------------------------
# Two-player builder
# ----------------------------------------------------------------------------

# Concrete board layout used by the spec example:
#
#         1a (private to A)
#         |
#  1b -- [2] -- 3b              (pole 2 is the shared pole, pole 3a/b are goals)
#         |
#         3a (private to A)
#
# Player A: starts on 1a (odd-sized disks), goal is 3a, sees {1a, 2, 3a}.
# Player B: starts on 1b (even-sized disks), goal is 3b, sees {1b, 2, 3b}.

_PLAYER_A: PlayerId = "A"
_PLAYER_B: PlayerId = "B"


def build_two_player_config(num_disks: int, *, max_turns: int = 1000) -> GameConfig:
    """Build the canonical 2-player Hanoi Crossing config.

    Player A owns odd disk sizes ``1, 3, 5, ...``; Player B owns even sizes
    ``2, 4, 6, ...``. Each player's start pole holds their N disks, largest at
    the bottom (so the smallest disk is on top, ready to be lifted).

    Raises:
        ConfigError: if ``num_disks <= 0`` or ``max_turns <= 0``.
    """
    if num_disks <= 0:
        raise ConfigError(f"num_disks must be > 0, got {num_disks}")
    # max_turns is also validated in GameConfig.__post_init__, but we surface
    # it here for a clearer call-site error.
    if max_turns <= 0:
        raise ConfigError(f"max_turns must be > 0, got {max_turns}")

    players = (_PLAYER_A, _PLAYER_B)
    poles = (
        PoleSpec(
            id="1a",
            visible_to=frozenset({_PLAYER_A}),
            goal_for=frozenset(),
        ),
        PoleSpec(
            id="1b",
            visible_to=frozenset({_PLAYER_B}),
            goal_for=frozenset(),
        ),
        PoleSpec(
            id="2",
            visible_to=frozenset({_PLAYER_A, _PLAYER_B}),
            goal_for=frozenset(),
        ),
        PoleSpec(
            id="3a",
            visible_to=frozenset({_PLAYER_A}),
            goal_for=frozenset({_PLAYER_A}),
        ),
        PoleSpec(
            id="3b",
            visible_to=frozenset({_PLAYER_B}),
            goal_for=frozenset({_PLAYER_B}),
        ),
    )

    a_disks = tuple(range(2 * num_disks - 1, 0, -2))  # e.g. N=3 -> (5, 3, 1)
    b_disks = tuple(range(2 * num_disks, 0, -2))      # e.g. N=3 -> (6, 4, 2)
    initial_stacks: dict[PoleId, tuple[int, ...]] = {
        "1a": a_disks,
        "1b": b_disks,
        "2": (),
        "3a": (),
        "3b": (),
    }

    disk_owner: dict[int, PlayerId] = {}
    for d in a_disks:
        disk_owner[d] = _PLAYER_A
    for d in b_disks:
        disk_owner[d] = _PLAYER_B

    return GameConfig(
        players=players,
        poles=poles,
        initial_stacks=initial_stacks,
        disk_owner=disk_owner,
        max_turns=max_turns,
    )
