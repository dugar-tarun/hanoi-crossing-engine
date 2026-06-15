from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .actions import SKIP, Action, Lift, Place, _Skip
from .config import GameConfig, PlayerId, PoleId
from .rules import hanoi_placement_legal, is_won_for
from .state import GameState, Status, _freeze_hands, _freeze_poles


class IllegalReason(Enum):
    POLE_NOT_VISIBLE = auto()
    HAND_OCCUPIED = auto()
    HAND_EMPTY = auto()
    POLE_EMPTY = auto()
    PLACEMENT_RULE = auto()
    GAME_OVER = auto()
    UNKNOWN_PLAYER = auto()


class Terminal(Enum):
    WON = auto()
    DRAW = auto()


@dataclass(frozen=True, slots=True)
class StepResult:
    legal: bool
    illegality: IllegalReason | None  # set iff legal is False
    terminal: Terminal | None  # set iff state became WON or DRAW on this call
    winner: PlayerId | None  # set iff terminal is Terminal.WON


def initial_state(config: GameConfig) -> GameState:
    """Materialize the starting ``GameState`` from a ``GameConfig``.

    Pole stacks are copied from ``config.initial_stacks``, every hand is empty,
    and both counters start at zero. A player already satisfying the win
    predicate (checked in ``config.players`` order) wins immediately.
    """
    poles = _freeze_poles({pid: tuple(stack) for pid, stack in config.initial_stacks.items()})
    hands = _freeze_hands({p: None for p in config.players})
    base = GameState(
        config=config,
        poles=poles,
        hands=hands,
        status=Status.IN_PROGRESS,
        winner=None,
        step_count=0,
        attempt_count=0,
    )
    for p in config.players:
        if is_won_for(base, p):
            return GameState(
                config=config,
                poles=poles,
                hands=hands,
                status=Status.WON,
                winner=p,
                step_count=0,
                attempt_count=0,
            )
    return base


def is_terminal(state: GameState) -> bool:
    return state.status is not Status.IN_PROGRESS


def legal_actions(state: GameState, player: PlayerId) -> tuple[Action, ...]:
    """Enumerate the actions ``player`` may legally submit in ``state``.

    Returns ``()`` for a terminal state or an unknown player. Otherwise the
    result is non-empty, emitted in pole-id sorted order with ``SKIP`` last.
    """
    if is_terminal(state):
        return ()
    if player not in state.config.players:
        return ()

    held = state.hands[player]
    actions: list[Action] = []
    visible_pole_ids = sorted(spec.id for spec in state.config.poles if player in spec.visible_to)
    if held is None:
        for pid in visible_pole_ids:
            if state.poles[pid]:
                actions.append(Lift(pid))
    else:
        for pid in visible_pole_ids:
            if hanoi_placement_legal(state.poles[pid], held):
                actions.append(Place(pid))
    actions.append(SKIP)
    return tuple(actions)


def _illegal(state: GameState, reason: IllegalReason) -> tuple[GameState, StepResult]:
    """Build the ``(state, StepResult)`` pair for an illegal step.

    Increments ``attempt_count``, leaves all game-state fields unchanged, and
    promotes to ``DRAW`` if the cap is now reached.
    """
    new_attempt = state.attempt_count + 1
    if new_attempt >= state.config.max_turns:
        new_state = GameState(
            config=state.config,
            poles=state.poles,
            hands=state.hands,
            status=Status.DRAW,
            winner=None,
            step_count=state.step_count,
            attempt_count=new_attempt,
        )
        return new_state, StepResult(
            legal=False, illegality=reason, terminal=Terminal.DRAW, winner=None
        )
    new_state = GameState(
        config=state.config,
        poles=state.poles,
        hands=state.hands,
        status=state.status,
        winner=state.winner,
        step_count=state.step_count,
        attempt_count=new_attempt,
    )
    return new_state, StepResult(legal=False, illegality=reason, terminal=None, winner=None)


def _can_act_on_pole(state: GameState, player: PlayerId, pole: PoleId) -> bool:
    spec = state.config._pole_index.get(pole)
    if spec is None:
        return False
    return player in spec.visible_to


def step(state: GameState, player: PlayerId, action: Action) -> tuple[GameState, StepResult]:
    """Apply ``action`` taken by ``player`` to ``state``; return the next state.

    The engine never raises for game-rule violations; it returns
    ``StepResult(legal=False, illegality=...)`` and leaves the game state
    unchanged. A non-``Action`` value raises ``TypeError``.
    """
    if is_terminal(state):
        return state, StepResult(
            legal=False,
            illegality=IllegalReason.GAME_OVER,
            terminal=None,
            winner=None,
        )

    if player not in state.config.players:
        return _illegal(state, IllegalReason.UNKNOWN_PLAYER)

    if isinstance(action, _Skip):
        return _commit_legal(state, dict(state.poles), dict(state.hands), win_check_player=None)
    if isinstance(action, Lift):
        return _apply_lift(state, player, action.pole)
    if isinstance(action, Place):
        return _apply_place(state, player, action.pole)
    raise TypeError(f"unknown action type: {type(action).__name__} (expected Lift | Place | _Skip)")


def _apply_lift(state: GameState, player: PlayerId, pole: PoleId) -> tuple[GameState, StepResult]:
    if not _can_act_on_pole(state, player, pole):
        return _illegal(state, IllegalReason.POLE_NOT_VISIBLE)
    if state.hands[player] is not None:
        return _illegal(state, IllegalReason.HAND_OCCUPIED)
    stack = state.poles[pole]
    if not stack:
        return _illegal(state, IllegalReason.POLE_EMPTY)

    new_stack = stack[:-1]
    disk = stack[-1]
    new_poles = dict(state.poles)
    new_poles[pole] = new_stack
    new_hands = dict(state.hands)
    new_hands[player] = disk
    return _commit_legal(state, new_poles, new_hands, win_check_player=None)


def _apply_place(state: GameState, player: PlayerId, pole: PoleId) -> tuple[GameState, StepResult]:
    if not _can_act_on_pole(state, player, pole):
        return _illegal(state, IllegalReason.POLE_NOT_VISIBLE)
    held = state.hands[player]
    if held is None:
        return _illegal(state, IllegalReason.HAND_EMPTY)
    stack = state.poles[pole]
    if not hanoi_placement_legal(stack, held):
        return _illegal(state, IllegalReason.PLACEMENT_RULE)

    new_stack = stack + (held,)
    new_poles = dict(state.poles)
    new_poles[pole] = new_stack
    new_hands = dict(state.hands)
    new_hands[player] = None
    return _commit_legal(state, new_poles, new_hands, win_check_player=player)


def _commit_legal(
    state: GameState,
    new_poles: dict[PoleId, tuple[int, ...]],
    new_hands: dict[PlayerId, int | None],
    win_check_player: PlayerId | None,
) -> tuple[GameState, StepResult]:
    """Build the next state after a legal action and assemble the StepResult."""
    new_attempt = state.attempt_count + 1
    new_step = state.step_count + 1

    candidate = GameState(
        config=state.config,
        poles=_freeze_poles(new_poles),
        hands=_freeze_hands(new_hands),
        status=Status.IN_PROGRESS,
        winner=None,
        step_count=new_step,
        attempt_count=new_attempt,
    )

    # Win is only checked after a successful Place, with the actor evaluated
    # first so ties resolve in their favour.
    if win_check_player is not None:
        candidates = [win_check_player] + [p for p in state.config.players if p != win_check_player]
        for p in candidates:
            if is_won_for(candidate, p):
                won = GameState(
                    config=state.config,
                    poles=candidate.poles,
                    hands=candidate.hands,
                    status=Status.WON,
                    winner=p,
                    step_count=new_step,
                    attempt_count=new_attempt,
                )
                return won, StepResult(
                    legal=True,
                    illegality=None,
                    terminal=Terminal.WON,
                    winner=p,
                )

    if new_attempt >= state.config.max_turns:
        drawn = GameState(
            config=state.config,
            poles=candidate.poles,
            hands=candidate.hands,
            status=Status.DRAW,
            winner=None,
            step_count=new_step,
            attempt_count=new_attempt,
        )
        return drawn, StepResult(
            legal=True,
            illegality=None,
            terminal=Terminal.DRAW,
            winner=None,
        )

    return candidate, StepResult(legal=True, illegality=None, terminal=None, winner=None)
