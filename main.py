from collections import Counter
import json
import random
import traceback
from ollama import generate


class LlmPlayer():
    context = """
        Cockroach Poker is a game played with a special deck of 64 cards which feature 8 creature types (COCKROACH, BAT, FLY, FROG, RAT, SCORPION, SPIDER, and STINKBUG). There are exactly 8 cards of each type. The deck is shuffled and dealt evenly between all players. The first player chooses a card from their hand and passes it to any other player face down, claiming it to be a specific type of card. The receiving player can either accept or pass:
        Accept: announce whether they believe the statement is a lie or not and then accept the card. If the player's belief is correct then the passing player takes back the card, and if its incorrect then the receiving player takes it. The card is then laid out face up in front of the respective player.
        Pass: look at the card and pass it to another player, again specifying a type. This statement does not have to match the previous player's claim. Cards not be passed to players who have already seen the card.
        The card moves from player to player until a player accepts the card or until only one player has not seen it. The last player must then accept the card and guess whether or not the passing player's statement is true. The player who lost the last round and received the face up card is the starting player of the next round.
        The game ends when a player has four cards of the same type in front of them, or when a player has no more cards in their hand and has to play a card. In both cases, that player loses the game while all other players win.
        
    """

    finetune_instructions = """
        More instructions and tips:
        Having cards face-up in front of you is bad. 
        If you pass a card, other players cannot pass that card back to you that round. 
        If you look at a card, you must pass it to another player and cannot guess it.
        You must return only a valid JSON object.
        If PLAYing or PASSing a card, the 'card' key must contain a SINGLE card name, without any numbers.
        If PLAYing a card, make sure you are playing a card you have in your hand, NOT from the face-up cards on the table.
        Make sure you spell other players' names correctly.
        You cannot pass a card back to the person who passed it to you.
        Make sure you have all required keys in your output.
        Do not escape single quotes or apostrophes. e.g. use don't instead of don\\'t.
        You can lie when passing a card, but do not have to. You can tell the truth and claim that the card is what it actually is.
        Other players can tell the truth when claiming what a card is. They do not have to lie.
    """

    def __init__(self, name):
        self.name = name
        self.context += f"\nYour name is {name} and you are playing a game of Cockroach Poker."

    def generate_json_format(self, required_keys):
        # Generate a JSON schema for the response.
        return {
        "type": "object",
        "properties": {
            "player": {
                "type": "string"
            },
            "action": {
                "type": "string"
            },
            "target": {
                "type": "string"
            },
            "card": {
                "type": "string"
            },
            "claim": {
                "type": "string"
            },
            "guess": {
                "type": "string"
            },
            "reason": {
                "type": "string"
            },
        },
        "required": required_keys
    }

    def play(self, game_state, instructions, required_keys):
        # Play move by getting a response from the LLM, given some context.
        # print("!!! PROMPT !!!", instructions)
        generate_response = generate(
            model = self.name,
            prompt = '\n'.join([self.context, game_state, instructions, self.finetune_instructions]),
            format = self.generate_json_format(required_keys)
        )
        return generate_response.response


class Move:
    # Class to store player moves in a structured format.
    valid_moves = ["PLAY", "LOOK", "PASS", "GUESS", "FORFEIT"]
    max_player_length = 20
    max_action_length = 7
    max_card_length = 9
    max_guess_length = 7

    def __init__(self, player, action, target, card, claim, guess, reason):
        self.player = player
        self.action = action
        self.target = target if target else ""
        self.card = card if card else "" 
        self.claim = claim if claim else ""
        self.guess = guess if guess else ""
        self.reason = reason if reason else ""

    @staticmethod
    def rtrunc(s, width):
        # Truncate, then right-justify, to a given width.
        return s[:width].rjust(width)

    def get_loser(self):
        if self.action == "FORFEIT":
            return 

    def __str__(self):
        # Readable representation of an action.
        if self.action == "FORFEIT":
            return f"{self.player} forfeits their turn with an invalid response."
        elif self.action == "PLAY":
            return f"{self.player} gives a {self.card} to {self.target} and claims it is a {self.claim}."
        elif self.action == "LOOK":
            return f"{self.player} looks at the {self.card}."
        elif self.action == "PASS":
            return f"{self.player} passes the {self.card} to {self.target} and claims it is a {self.claim}."
        elif self.action == "GUESS":
            guess = (self.guess == "TRUE")
            guess_is_correct = (guess and self.card == self.claim) or (not guess and self.card != self.claim)
            if guess_is_correct:
                return f"{self.player} correctly guessed that {self.target} {"lied" if self.card != self.claim else "told the truth"} about the {self.card}."
            else:
                return f"{self.player} incorrectly thought that {self.target} was {"telling the truth" if self.card != self.claim else "lying"} about the {self.card}. The claim was in fact {"true" if self.card == self.claim else "false"}."


    def __repr__(self):
        # Full representation of an action. Intended to be used for logging.
        return " ".join([
            self.rtrunc(self.player, Move.max_player_length),
            self.rtrunc(self.action, Move.max_action_length),
            self.rtrunc(self.target, Move.max_player_length),
            self.rtrunc(self.card, Move.max_card_length),
            self.rtrunc(self.claim, Move.max_card_length),
            self.rtrunc(self.guess, Move.max_guess_length),
        ])
    
    @staticmethod
    def print_header():
        # Print out the header for the __repr__ format.
        return " ".join([
            Move.rtrunc("PLAYER", Move.max_player_length),
            Move.rtrunc("ACTION", Move.max_action_length),
            Move.rtrunc("TARGET", Move.max_player_length),
            Move.rtrunc("CARD", Move.max_card_length),
            Move.rtrunc("CLAIM", Move.max_card_length),
            Move.rtrunc("GUESS", Move.max_guess_length),
        ])


class Runner:
    # Runs games of Cockroach Poker with the same players.
    types = ["COCKROACH", "BAT", "FLY", "FROG", "RAT", "SCORPION", "SPIDER", "STINKBUG"]
    deck = types * 8

    def __init__(self, model_names):
        self.players = {model_name: LlmPlayer(model_name) for model_name in model_names}  # map of player names -> Player objects.
        self.losses = Counter()
        self.set_up_game()

    def chunk_cards_equally(self):
        # Generator to yield equally-sized chunks of a deck.
        k, m = divmod(len(self.deck), len(self.players))
        for i in range(len(self.players)):
            yield self.deck[i*k+min(i, m):(i+1)*k+min(i+1, m)]

    def set_up_game(self, starting_player=None):
        # Set up a new game by dealing out cards and picking a player to start.
        random.shuffle(self.deck)  # shuffle deck in-place.
        self.player_hands = {player: Counter(chunk) for (player, chunk) in zip(self.players.keys(), self.chunk_cards_equally())}  # map of player names -> player cards (hidden).
        self.player_revealed = {player: Counter() for player in self.players.keys()}  # map of player names -> table cards (revealed).
        if starting_player:
            self.current_player = starting_player  # use provided starting player.
        else:
            self.current_player = random.choice(list(self.players.keys()))  # pick random starting player.

    def get_enumerated_cards(self, counter):
        # Return a string of enumerated cards in alphabetical order, e.g. "1x COCKROACH, 3x SCORPION, 1x STINKBUG."
        return ", ".join(f"{count}x {card}" for (card, count) in sorted(counter.items()) if count > 0)

    def write_revealed_state(self, current_player_name):
        # Write the current state of revealed cards as a string.
        # e.g. "In front of you are 2x BAT, 4x RAT, 1x SCORPION."
        state = ["The following cards are revealed face-up on the table:"]
        for player, revealed in self.player_revealed.items():
            state.append(f"\nIn front of player {"(you)" if player == current_player_name else ""} are: {self.get_enumerated_cards(revealed)}.")
        return "\n".join(state)

    def check_for_loser(self):
        # Check if anyone has lost the game. If so, return their name. Otherwise, return None.
        for player, hand in self.player_hands.items():
            if sum(hand.values()) == 0:  # no more cards in hand.
                return player, "No more cards in hand"
        for player, revealed in self.player_revealed.items():
            for card, count in revealed.items():
                if count == 4:  # four of the type.
                    return player, f"4x {card}"
        return None, None

    def get_response_from_current_player(self, instructions, required_keys):
        # Get the parsed response from the current player.
        raw_response = self.players[self.current_player].play(
            self.write_revealed_state(self.current_player), 
            instructions,
            required_keys
        )
        raw_response = raw_response[raw_response.find("{"):raw_response.rfind("}")+1]  # trim to brackets.
        response = json.loads(raw_response)
        print("> " + self.current_player + " says: '" + response.get("reason", "[No reason given]") + "'")
        return response
    
    def get_all_claims_this_round(self, history):
        # Get all claims made in the current round, as a string in the form:
        # [player] passed it to [player] and claimed it was a [card].
        # [player] passed it to you and claimed it was a [card].
        all_claims = ["So far this round:"]
        for move in history[::-1]:
            if move.action in ["PLAY", "PASS"]:
                all_claims.append(f"{move.player} passed a card to {'you' if move.target == self.current_player else move.target} and claimed it was a {move.claim}.")
                if move.action == "PLAY":
                    break
        return " ".join(all_claims)

    def play_move(self, valid_targets, history):
        if len(valid_targets) == len(self.players) - 1:  # first move of the round. Must attack.
            instructions = "\n".join([
                f"You must play one of the cards from your hand: {self.get_enumerated_cards(self.player_hands[self.current_player])}.",
                f"You can target the following players: {", ".join(valid_targets)}.",
                f"You can claim your card is any one of the following: {self.types}.",
                "Return a raw JSON object as a string with the keys 'card' (only the card you want to play, do not include the '1x', '2x', etc. count), 'target' (the player you want to pass to), 'claim' (the bug you claim your card is, you can either tell the truth or lie), and 'reason' (the reason why you chose this move)."
            ])
            required_keys = ["card", "target", "claim", "reason"]
            try:
                response = self.get_response_from_current_player(instructions, required_keys)
                for key in ["card", "target", "claim", "reason"]:
                    if key not in response:
                        raise ValueError(f"Missing key '{key}' in response.")
                if response["target"] not in valid_targets:
                    raise ValueError(f"Player {response['target']} is not a valid target.")
                if response["card"] not in self.types:
                    raise ValueError(f"Player {self.current_player} tried to play a {response['card']}, an invalid type.")
                if response["card"] not in self.player_hands[self.current_player] or self.player_hands[self.current_player][response["card"]] < 1:
                    raise ValueError(f"Player {self.current_player} does not have {response['card']} in their hand.")
                if response["claim"] not in self.types:
                    raise ValueError(f"Player {self.current_player} claimed their card was a {response['claim']}, an invalid type.")
                self.player_hands[self.current_player][response["card"]] -= 1  # decrement card count.
                return Move(self.current_player, "PLAY", response["target"], response["card"], response["claim"], None, response["reason"])
            except Exception as e:
                print(e, traceback.format_exc())
                return Move(self.current_player, "FORFEIT", None, None, None, None, f"Error parsing response: {e}")
        elif len(valid_targets) == 0:  # forced last move of the round. Must guess.
            last_move = history[-1]
            instructions = "\n".join([
                self.get_all_claims_this_round(history),
                f"You must determine whether the last claim — {last_move.player} claiming that the card they passed to you is a {last_move.claim} — is TRUE or FALSE.",
                f"Return a raw JSON object as a string with the keys 'guess' (TRUE if you think {last_move.player} is telling the truth, or FALSE if you think {last_move.player} is lying), and 'reason' (the reason why you think so)."
            ])
            required_keys = ["guess", "reason"]
            try:
                response = self.get_response_from_current_player(instructions, required_keys)
                for key in ["guess", "reason"]:
                    if key not in response:
                        raise ValueError(f"Missing key '{key}' in response.")
                if type(response["guess"]) == bool:  # cast bool to string in case it was sent as a bool.
                    response["guess"] = "TRUE" if response["guess"] else "FALSE"
                if type(response["guess"]) != str:  # check if guess is a string.
                    raise ValueError(f"Guess must be a string.")
                response["guess"] = response["guess"].upper()
                if response["guess"] not in ["TRUE", "FALSE"]:
                    raise ValueError(f"Guess must be either TRUE or FALSE.")
                return Move(self.current_player, "GUESS", last_move.player, last_move.card, last_move.claim, response["guess"], response["reason"])
            except Exception as e:
                print(e, traceback.format_exc())
                return Move(self.current_player, "FORFEIT", None, last_move.card, None, None, f"Error parsing response: {e}")
        elif history[-1].action == "LOOK":  # looked at card last round, must pass.
            last_move = history[-1]
            instructions = "\n".join([
                self.get_all_claims_this_round(history),
                f"You looked at the card that {last_move.target} passed to you and claimed it was a {last_move.claim}. It {'really is' if last_move.claim == last_move.card else 'is actually'} a {last_move.card}.",
                f"You need to pass the card to another player. You can pass to the following players: {", ".join(valid_targets)}."
                f"You can claim your card is any one of the following: {self.types}.",
                f"But remember, {last_move.target} claimed the card was a {last_move.claim}.",
                "Return a raw JSON object as a string with the keys 'target' (the player you want to pass to), 'claim' (what you claim your card is, you can tell the truth or lie), and 'reason' (the reason why you chose this move)."
            ])
            required_keys = ["target", "claim", "reason"]
            try:
                response = self.get_response_from_current_player(instructions, required_keys)
                for key in ["target", "claim", "reason"]:
                    if key not in response:
                        raise ValueError(f"Missing key '{key}' in response.")
                if response["target"] not in valid_targets:
                    raise ValueError(f"Player {response['target']} is not a valid target.")
                if response["claim"] not in self.types:
                    raise ValueError(f"Player {response['target']} claimed their card was a {response['claim']}, an invalid type.")
                return Move(self.current_player, "PASS", response["target"], last_move.card, last_move.claim, None, response["reason"])
            except Exception as e:
                print(e, traceback.format_exc())
                return Move(self.current_player, "FORFEIT", None, last_move.card, None, None, f"Error parsing response: {e}")
        else:  # can decide whether to LOOK at card or GUESS.
            last_move = history[-1]
            instructions = "\n".join([
                self.get_all_claims_this_round(history),
                "You can either LOOK at the card and pass it to another player, or try to GUESS whether this claim is TRUE or FALSE.",
                "If you want to LOOK at the card and pass it to another player, return a raw JSON object as a string with the keys 'action' (set to 'LOOK'), 'claim' (set to 'NONE'), 'guess' (set to 'NONE') and 'reason' (the reason why you want to look and pass the card.",
                f"If you want to GUESS whether this claim is TRUE or FALSE, return a raw JSON object as a string with the keys 'action' (set to GUESS), 'claim' (set to 'NONE'),'guess' (TRUE if you think {last_move.player} is telling the truth, or FALSE if you think {last_move.player} is lying), and 'reason' (the reason why you think so)."
            ])
            required_keys = ["action", "claim", "guess", "reason"]
            try:
                response = self.get_response_from_current_player(instructions, required_keys)
                if "action" in response and response["action"] == "LOOK":  # chose to LOOK.
                    return Move(self.current_player, "LOOK", last_move.player, last_move.card, last_move.claim, None, response["reason"])
                else:  # chose to GUESS.
                    for key in ["guess", "reason"]:
                        if key not in response:
                            raise ValueError(f"Missing key '{key}' in response.")
                    if type(response["guess"]) == bool:  # cast bool to string in case it was sent as a bool.
                        response["guess"] = "TRUE" if response["guess"] else "FALSE"
                    if type(response["guess"]) != str:  # check if guess is a string.
                        raise ValueError(f"Guess must be a string.")
                    response["guess"] = response["guess"].upper()
                    if response["guess"] not in ["TRUE", "FALSE"]:
                        raise ValueError(f"Guess must be either TRUE or FALSE.")
                    return Move(self.current_player, "GUESS", last_move.player, last_move.card, last_move.claim, response["guess"], response["reason"])
            except Exception as e:
                print(e, traceback.format_exc())
                return Move(self.current_player, "FORFEIT", None, last_move.card, None, None, f"Error parsing response: {e}")
            

    def play_round(self):
        # Play a round in an ongoing game; i.e. a series of moves until one player puts a card in front of them.
        # Return the name of the losing player, and the move history for that round.
        valid_targets = [player for player in self.players.keys() if player != self.current_player]  # players that the current player can target by passing.
        history = []
        while True:
            move = self.play_move(valid_targets, history)
            print(move)
            history.append(move)
            if move.action in ["PLAY", "PASS"]:
                self.current_player = move.target
                valid_targets = [player for player in valid_targets if player != self.current_player]  # remove targeted player from list of valid targets.
            elif move.action == "GUESS":  # round end. See who loses.
                guess = (move.guess == "TRUE")
                guess_is_correct = (guess and move.card == move.claim) or (not guess and move.card != move.claim)
                if guess_is_correct:  # guesser guessed correctly.
                    self.player_revealed[move.target][move.card] += 1  # add to the claimer's revealed cards.
                    self.current_player = move.target  # claimer loses, so goes first.
                    return move.target, history
                else:  # guesser guessed incorrectly.
                    self.player_revealed[move.player][move.card] += 1  # add to the guesser's revealed cards.
                    self.current_player = move.player  # guesser loses, so goes first.
                    return move.player, history
            elif move.action == "FORFEIT":  # round end by forfeit.
                if move.card == "":  # occasionally happens on first turn, when no card has been played yet.
                    move.card = random.choice(list(self.player_hands[self.current_player].keys()))  # get a random card from the player's hand.
                    self.player_hands[self.current_player][move.card] -= 1  # remove the card from the player's hand.
                self.player_revealed[move.player][move.card] += 1  # put the card in the revealed cards in front of them.
                self.current_player = move.player  # forfeiter loses, so goes first.
                return move.player, history
            else:  # we actually don't care about LOOK moves. Next cycle it will handle itself.
                pass

    def play_game(self):
        # Set up and play a full game.
        self.set_up_game()
        history = []
        while True:
            # Check if anyone has lost.
            losing_player, losing_reason = self.check_for_loser()
            if losing_player is not None:
                self.losses[losing_player] += 1
                print(f"Player {losing_player} loses: {losing_reason}!")
                print("Face-up cards:")  # print revealed cards.
                for player, revealed in self.player_revealed.items():
                    print(f"  {player} has: {self.get_enumerated_cards(revealed)}.")
                break

            # Otherwise, play a round.
            print(f"New round, {self.current_player} goes first.")
            round_loser, moves = self.play_round()
            losing_card = moves[-1].card
            print(f"{round_loser} lost that round and takes the {losing_card}.\n")
            Move.print_header()
            for m in moves:
                print(m.__repr__())
            history.extend(moves)
        return history

    def play_games(self, n):
        all_history = []
        for i in range(n):
            print(f"Game {i+1} of {n}...")
            history = self.play_game()
            all_history.append(history)
            print(f"Game {i+1} of {n} complete.")
            losses_array = [f"{player}: {losses}" for player, losses in self.losses.items()]
            print(f"  Losses: {", ".join(losses_array)}")
            print("\n\n")
        



runner = Runner(["gemma3:4b", "qwen2.5:7b", "llama3.1:8b"])
runner.play_games(100)