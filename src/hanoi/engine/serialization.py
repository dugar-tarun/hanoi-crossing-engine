"""JSON-friendly ``to_dict`` / ``from_dict`` codecs for the engine value types.

The codec is intentionally explicit — no third-party dataclass/JSON glue.
Round-tripping is exact for ``GameConfig``, ``GameState``, and ``Action``.
"""

from __future__ import annotations

from typing import Any

from .actions import Action, Lift, Place, SKIP, _Skip
from .config import GameConfig, PlayerId, PoleId, PoleSpec
from .state import GameState, Status, _freeze_hands, _freeze_poles


# ----------------------------------------------------------------------------
# Action
# ----------------------------------------------------------------------------

def action_to_dict(action: Action) -> dict[str, Any]:
    if isinstance(action, _Skip):
        return {"type": "skip"}
    if isinstance(action, Lift):
        return {"type": "lift", "pole": action.pole}
    if isinstance(action, Place):
        return {"type": "place", "pole": action.pole}
    raise TypeError(f"unknown action type: {type(action).__name__}")


def action_from_dict(data: dict[str, Any]) -> Action:
    kind = data.get("type")
    if kind == "skip":
        return SKIP
    if kind == "lift":
        return Lift(pole=str(data["pole"]))
    if kind == "place":
        return Place(pole=str(data["pole"]))
    raise ValueError(f"unknown action dict: {data!r}")


# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

def pole_spec_to_dict(spec: PoleSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "visible_to": sorted(spec.visible_to),
        "goal_for": sorted(spec.goal_for),
    }


def pole_spec_from_dict(data: dict[str, Any]) -> PoleSpec:
    return PoleSpec(
        id=str(data["id"]),
        visible_to=frozenset(data["visible_to"]),
        goal_for=frozenset(data["goal_for"]),
    )


def config_to_dict(config: GameConfig) -> dict[str, Any]:
    return {
        "players": list(config.players),
        "poles": [pole_spec_to_dict(p) for p in config.poles],
        # Lists, not tuples, so the dict is JSON-encodable as-is.
        "initial_stacks": {pid: list(stack) for pid, stack in config.initial_stacks.items()},
        # Disk owner keys are ints; JSON requires string keys, so we stringify.
        "disk_owner": {str(d): owner for d, owner in config.disk_owner.items()},
        "max_turns": config.max_turns,
    }


def config_from_dict(data: dict[str, Any]) -> GameConfig:
    return GameConfig(
        players=tuple(data["players"]),
        poles=tuple(pole_spec_from_dict(p) for p in data["poles"]),
        initial_stacks={pid: tuple(stack) for pid, stack in data["initial_stacks"].items()},
        disk_owner={int(d): owner for d, owner in data["disk_owner"].items()},
        max_turns=int(data["max_turns"]),
    )


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------

def state_to_dict(state: GameState, *, include_config: bool = True) -> dict[str, Any]:
    """Serialize a ``GameState``.

    ``include_config=True`` produces a self-contained snapshot that can be
    reconstructed without external context. Pass ``False`` if you intend to
    pair the state dict with a separately-serialized config, e.g. when storing
    many states from a single game.
    """
    payload: dict[str, Any] = {
        "poles": {pid: list(stack) for pid, stack in state.poles.items()},
        "hands": dict(state.hands),
        "status": state.status.name,
        "winner": state.winner,
        "step_count": state.step_count,
        "attempt_count": state.attempt_count,
    }
    if include_config:
        payload["config"] = config_to_dict(state.config)
    return payload


def state_from_dict(
    data: dict[str, Any], *, config: GameConfig | None = None
) -> GameState:
    cfg = config if config is not None else config_from_dict(data["config"])
    return GameState(
        config=cfg,
        poles=_freeze_poles({pid: tuple(stack) for pid, stack in data["poles"].items()}),
        hands=_freeze_hands(dict(data["hands"])),
        status=Status[data["status"]],
        winner=data.get("winner"),
        step_count=int(data["step_count"]),
        attempt_count=int(data["attempt_count"]),
    )
