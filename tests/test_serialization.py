"""Round-trip tests for ``to_dict`` / ``from_dict`` codecs."""

from __future__ import annotations

import json

from hanoi.engine import (
    SKIP,
    Lift,
    Place,
    action_from_dict,
    action_to_dict,
    build_two_player_config,
    config_from_dict,
    config_to_dict,
    initial_state,
    state_from_dict,
    state_to_dict,
    step,
)


def test_action_roundtrip() -> None:
    for original in (Lift("1a"), Place("3b"), SKIP):
        data = action_to_dict(original)
        json.dumps(data)  # Must be JSON-serializable.
        assert action_from_dict(data) == original


def test_config_roundtrip() -> None:
    cfg = build_two_player_config(3, max_turns=42)
    data = config_to_dict(cfg)
    json.dumps(data)
    rebuilt = config_from_dict(data)

    assert rebuilt.players == cfg.players
    assert rebuilt.poles == cfg.poles
    assert dict(rebuilt.initial_stacks) == dict(cfg.initial_stacks)
    assert dict(rebuilt.disk_owner) == dict(cfg.disk_owner)
    assert rebuilt.max_turns == cfg.max_turns


def test_state_roundtrip_self_contained() -> None:
    cfg = build_two_player_config(2)
    s0 = initial_state(cfg)
    s1, _ = step(s0, "A", Lift("1a"))
    s2, _ = step(s1, "A", Place("2"))  # disk 1 onto pole 2.

    data = state_to_dict(s2)
    json.dumps(data)
    rebuilt = state_from_dict(data)

    assert dict(rebuilt.poles) == dict(s2.poles)
    assert dict(rebuilt.hands) == dict(s2.hands)
    assert rebuilt.status is s2.status
    assert rebuilt.winner == s2.winner
    assert rebuilt.step_count == s2.step_count
    assert rebuilt.attempt_count == s2.attempt_count


def test_state_roundtrip_with_external_config() -> None:
    cfg = build_two_player_config(1)
    s0 = initial_state(cfg)
    data = state_to_dict(s0, include_config=False)
    assert "config" not in data
    rebuilt = state_from_dict(data, config=cfg)
    assert dict(rebuilt.poles) == dict(s0.poles)
    assert rebuilt.config is cfg
