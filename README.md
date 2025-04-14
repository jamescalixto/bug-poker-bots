# Cockroach Poker for LLMs

Inspired by [LLM Mafia Game Competition](https://mafia.opennumbers.xyz/). Makes LLMs (via Ollama) play [Cockroach Poker](https://boardgamegeek.com/boardgame/11971/cockroach-poker) against each other.

## Usage

Download [Ollama](https://ollama.com/) and install some models.

Edit the Runner call to call models you have installed, e.g.:

```
runner = Runner(["gemma3:12b", "qwen2.5:14b", "phi4:14b", "mistral-nemo:12b"])
```

Then run `main.py` and watch the console output.

## Notes on logic

The `Move` object has the following fields. Note that `Move` objects are created by the runner and not the `LlmPlayer` objects themselves, so they are not exposed to spoilers (e.g. the identity of the card during a `GUESS` action).

### `player`

Mandatory. Indicates the player whose turn it is.

### `action`

Mandatory. Indicates the action the player is taking. Can be one of:

- `PLAY`: player chooses a card to pass to another player to start off a round. Every round is guaranteed to start with a `PLAY` action.
- `LOOK`: player looks at the card. Player must `PASS` after looking at the card. Player cannot `LOOK` if there is only one other person remaining in the round.
- `PASS`: player passes the card to another person.
- `GUESS`: player guesses what the card passed to it is. Every round is guaranteed to end with a `GUESS` or a `FORFEIT` action.
- `FORFEIT`: only set by the runner if the LLM response is invalid. Player instantly loses. Every round is guaranteed to end with a `GUESS` or a `FORFEIT` action.

### `target`

Indicates the counterparty of the action. If the action is `PLAY` or `PASS` then it indicates the recipient of the card. If the action is `LOOK` or `GUESS` then it indicates the person who passed the card to the player.

### `card`

Indicates the identity of the card being passed, looked at, or guessed.

### `claim`

Indicates what the person passing the card has claimed it to be.

### `guess`

Is `TRUE` if the player guesses that the `claim` is true, or `FALSE` if the player guesses that the `claim` is a lie. This guess is correct if its boolean value is equal to the expression `card == claim` for that move.

### `reason`

Reason given by the LLM for making this move or guess. Often nonsensical, which is the fun part.