# Hanoi Crossing — Technical Requirements Document

## 1. Scope and Goals

Build a game engine for Hanoi Crossing that is correct, deterministic, and fully testable.
The engine enforces all game rules (legality, win detection, turn budgets) and exposes a clean public API for agents, replays, and frontends.

## 2. Key Rule Decisions

These are the interpretations the engine encodes; they will also be documented in the README.

- **Win condition (ownership + shared-pole cleared, full-state).** A player `p` wins iff, evaluated against the **complete `GameState`** (never against any observation):
  1. `state.hands[p] is None` — their hand is empty.
  2. Every disk `d` with `config.disk_owner[d] == p` sits on `p`'s designated goal pole (the unique pole whose `goal_for` contains `p`).
  3. No disk owned by `p` exists anywhere else in the game — not on any other private pole, not on the shared pole, not in any hand.
  4. Every pole visible to `p` other than `p`'s goal pole is completely empty (contains no disks of any ownership). In the 2-player layout this reduces to: the shared pole (pole 2) must be empty. An opponent disk parked on the shared pole blocks `p`'s win.

- **Disk parking is a first-class strategic mechanism.** The general action rules ("place onto any visible pole if Hanoi-legal") already permit a player to lift an opponent disk (from the shared pole, the only place they can reach it) and place it on their *own* private poles — including their own goal pole. Two consequences worth calling out:
  - A player may legally end a game with opponent disks interleaved into their goal-pole stack; this is fine for *their* win check (which is ownership-only) but those opponent disks are now permanently inaccessible to the opponent, since opponent private poles are non-visible to anyone else.
  - This makes "trapping" a viable strategy that the random agent will exercise occasionally. The engine encodes no policy about it; it simply allows the moves the spec permits.
- **Win check timing.** A win can be detected only at `initial_state` construction or immediately after a successful `Place`. `Skip`, `Lift`, and illegal actions never transition `Status` to `WON`. `initial_state` evaluates `is_won_for` for each player in `config.players` order; the first satisfying player wins. After construction, the engine checks the actor first; in any N-player generalization, ties resolve to the actor.
- **Illegal action semantics.** The engine reports `legal=False` with a structured `IllegalReason` and leaves the *game* state unchanged (poles, hands, status, `step_count`). The "turn wasted" cost is paid against the attempt budget: `state.attempt_count` advances on every `step()` call, legal or illegal; `state.step_count` advances *only* on legal actions.
- **Turn order remains external; turn *counting* is internal.** The engine still has no notion of "whose turn it is" — the caller passes the acting `player` on each `step()`. But the engine now owns the bounded turn budget so that termination is decidable from `GameState` alone.
- **Max-turn cap (DRAW termination).** `GameConfig.max_turns` is a hard upper bound on `state.attempt_count` — i.e., the total number of `step()` calls (legal or illegal). When `attempt_count` reaches `max_turns` without a winner, the engine transitions to `Status.DRAW` and rejects further actions with `IllegalReason.GAME_OVER`. `Status` therefore has three values: `IN_PROGRESS`, `WON`, `DRAW`. `build_two_player_config(num_disks)` sets a generous default of `max_turns = 1000` (overridable); construction rejects `max_turns <= 0`.
- **Disk identity = disk size** (globally unique integer). Player A: odd sizes, Player B: even sizes, both 1..2N.
- **Information hiding lives in the engine, but is orthogonal to win evaluation.** The engine exposes both full state and per-player `Observation` (for agents). Agents must use only `Observation` + `step`.

## 3. Engine Public API

All symbols below are re-exported from `hanoi.engine`.

### 3.1 `config.py`

```python
PlayerId = str
PoleId   = str

@dataclass(frozen=True)
class PoleSpec:
    id: PoleId
    visible_to: frozenset[PlayerId]    # who can see / act on this pole
    goal_for:   frozenset[PlayerId]    # winning destination for these players

@dataclass(frozen=True)
class GameConfig:
    players: tuple[PlayerId, ...]
    poles:   tuple[PoleSpec, ...]
    initial_stacks: Mapping[PoleId, tuple[int, ...]]   # bottom..top
    disk_owner:     Mapping[int, PlayerId]             # size -> owner
    max_turns:      int                                # hard cap; DRAW on reach

def build_two_player_config(num_disks: int, *, max_turns: int = 1000) -> GameConfig: ...

class ConfigError(ValueError): ...
```

**Invariants (enforced in `GameConfig.__post_init__`; violation raises `ConfigError`).** These are the only place in the engine that may raise after construction; every other engine function is total.

1. `len(players) >= 1` and `len(set(players)) == len(players)` (no duplicate player ids).
2. `len(poles) >= 1` and pole ids are unique: `len({p.id for p in poles}) == len(poles)`.
3. Every `PoleId` key in `initial_stacks` is present in `{p.id for p in poles}`, and every pole id has an entry in `initial_stacks` (possibly an empty tuple).
4. The disk set across all stacks is pairwise disjoint and equals `set(disk_owner.keys())` — every disk has exactly one owner, every owned disk is placed somewhere at start.
5. Every value in `disk_owner` appears in `players`.
6. For every `p in players`, exactly one `pole in poles` satisfies `p in pole.goal_for`. (Multi-goal or shared-goal variants would require relaxing this rule and updating `is_won_for`.)
7. For every `pole in poles`, `pole.visible_to` is a subset of `set(players)` and non-empty.
8. `max_turns > 0`.

`build_two_player_config` is responsible for producing a `GameConfig` that already satisfies all of these; if the caller passes `num_disks <= 0` it raises `ConfigError` before constructing the dataclass.

### 3.2 `state.py`

```python
class Status(Enum):
    IN_PROGRESS = auto()
    WON = auto()
    DRAW = auto()    # max_turns reached without a winner

@dataclass(frozen=True)
class GameState:
    config: GameConfig
    poles:  Mapping[PoleId, tuple[int, ...]]   # immutable; bottom..top
    hands:  Mapping[PlayerId, int | None]
    status: Status
    winner: PlayerId | None
    step_count:    int   # legal actions taken so far
    attempt_count: int   # all step() calls so far (legal + illegal); bounded by max_turns
```

Both counters start at `0`. `step_count` measures actual game progress; `attempt_count` is what the `max_turns` cap is enforced against. The two are equal iff no illegal action has ever been submitted.

`GameState` is a frozen dataclass; its `poles` mapping is a `MappingProxyType` over a private dict so callers can't mutate it. Each `step()` returns a new `GameState`; unchanged per-pole stacks are reused by reference (tuples are immutable) but the top-level `poles` mapping is rebuilt. Per-state size is `O(num_poles + num_disks)`.

### 3.3 `actions.py`

```python
@dataclass(frozen=True)
class Lift:  pole: PoleId
@dataclass(frozen=True)
class Place: pole: PoleId

@dataclass(frozen=True)
class _Skip:
    pass

SKIP: Final[_Skip] = _Skip()

Action = Lift | Place | _Skip
```

### 3.4 `engine.py`

```python
class IllegalReason(Enum):
    POLE_NOT_VISIBLE = auto()
    HAND_OCCUPIED    = auto()
    HAND_EMPTY       = auto()
    POLE_EMPTY       = auto()
    PLACEMENT_RULE   = auto()
    GAME_OVER        = auto()
    UNKNOWN_PLAYER   = auto()

class Terminal(Enum):
    WON  = auto()
    DRAW = auto()

@dataclass(frozen=True)
class StepResult:
    legal:       bool
    illegality:  IllegalReason | None  # set iff legal is False
    terminal:    Terminal | None       # set iff state.status became WON or DRAW on this call
    winner:      PlayerId | None       # set iff terminal is Terminal.WON

def initial_state(config: GameConfig) -> GameState: ...
def step(state: GameState, player: PlayerId, action: Action) -> tuple[GameState, StepResult]: ...
def legal_actions(state: GameState, player: PlayerId) -> tuple[Action, ...]: ...
def is_terminal(state: GameState) -> bool: ...
```

`initial_state(config)` materializes `poles` and `hands` from `config.initial_stacks` / empty hands, sets `step_count = attempt_count = 0`, and then evaluates `is_won_for` for each player in `config.players` order. If any player satisfies the predicate, the returned state has `status=Status.WON` and `winner=` that player (subsequent `step()` calls then return `IllegalReason.GAME_OVER`). Otherwise `status=Status.IN_PROGRESS, winner=None`.

`legal_actions(state, player)` returns `()` whenever `is_terminal(state)` is true, regardless of `player`. In any non-terminal state it returns a non-empty tuple that always contains `SKIP`. Callers (and `Observation.legal_actions` consumers) therefore use "empty tuple" as a structural terminal indicator, equivalent to `is_terminal(state)`.

Crucially, `step` does *not* take "current player" implicitly — the caller asserts who is acting, matching the spec's "turn order is external." Counter discipline per branch:

- Legal action (Lift / Place / Skip, including a winning Place): `attempt_count += 1` and `step_count += 1`.
- Illegal action: `attempt_count += 1` only; `step_count`, `poles`, `hands`, `status`, `winner` unchanged.

Reaching `max_turns` on either a legal or illegal step transitions the state to `Status.DRAW`. Both `legal` and `terminal` are reported independently on `StepResult` — a step that was both illegal *and* hit the cap on the same call produces `StepResult(legal=False, illegality=..., terminal=Terminal.DRAW, winner=None)`. Neither field hides the other; consumers branch on each independently.

**`rules.py` win predicate (concrete signature).** Kept here to make the ownership-only contract unambiguous:

```python
def goal_pole_of(config: GameConfig, player: PlayerId) -> PoleId: ...
def disks_owned_by(config: GameConfig, player: PlayerId) -> frozenset[int]: ...

def is_won_for(state: GameState, player: PlayerId) -> bool: ...
```

This is the *only* win check the engine uses, and it operates on full state by construction.

### 3.5 `observation.py`

```python
@dataclass(frozen=True)
class Observation:
    me: PlayerId
    visible_poles: Mapping[PoleId, tuple[int, ...]]
    own_hand: int | None
    step_count:    int
    attempt_count: int   # mirrors GameState; lets agents see how close DRAW is
    status: Status
    winner: PlayerId | None
    legal_actions: tuple[Action, ...]

def project(state: GameState, player: PlayerId) -> Observation: ...
```

## 4. Frontends

### 4.1 Replay (`modes/replay.py`)

Input JSON:

```json
{
  "schema_version": 1,
  "config": { "num_disks": 3, "max_turns": 1000 },
  "turn_order": ["A","B","A","B","A","B"],
  "moves": [
    {"type":"lift","pole":"1a"},
    {"type":"lift","pole":"1b"},
    {"type":"place","pole":"3a"}
  ]
}
```

`config.max_turns` is optional in the replay file; when omitted, the replay driver applies the `build_two_player_config` default (`1000`).

**Behavior.** Build config, iterate `turn_order`, pop the next move, call `engine.step`. Advance the turn cursor on every call (legal or illegal — Section 2 guarantees `attempt_count` already reflects this). Print the final `GameState` and a per-step log of `(player, action, StepResult)`. Exit `0` on a clean run, including runs where the engine returned `IllegalReason.*` results — illegal moves are valid replay content, not driver errors.

**Driver behavior — edge cases.** Malformed input cases listed below exit non-zero *before* the driver calls `engine.step()`. Engine-level results (legal or illegal) never produce a non-zero exit.

### 4.2 Random-play (`modes/random_play.py`)

```
hanoi-random --disks 3 --seed 42 --max-turns 5000 --turn-order ABAB...
```

`--max-turns` is forwarded directly into `GameConfig.max_turns`; the engine (not the CLI) enforces the cap and emits `Status.DRAW` if it is reached. A `RandomAgent` consumes only `Observation` + `engine.step`. It samples uniformly from `Observation.legal_actions`, which is non-empty in any non-terminal state and always contains `SKIP`. If `Observation.legal_actions` is empty the agent must not call `step()` — the driver is responsible for not scheduling further turns past a terminal state (it can detect this from `Observation.status` or, equivalently, from the empty `legal_actions`).
