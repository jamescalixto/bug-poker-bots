from collections import Counter
import json
import random
import traceback
from ollama import generate


class Player:
    def play(self, game_state, actions):
        pass


class LlmPlayer(Player):
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
        Telling the truth and lying are both good strategies.
    """

    def __init__(self, name):
        Player.__init__(self)
        self.name = name
        self.context += f"\nYour name is {name} and you are playing a game of Cockroach Poker."

    def generate_json_format(self, required_keys):
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
            "reason": {
                "type": "string"
            },
        },
        "required": required_keys
    }

    def play(self, game_state, instructions, required_keys):
        generate_response = generate(
            model = self.name,
            prompt = '\n'.join([self.context, game_state, instructions, self.finetune_instructions]),
            format = self.generate_json_format(required_keys)
        )
        return generate_response.response


class Move:
    # Class to store player moves in a structured format.
    valid_moves = ["PLAY", "LOOK", "PASS", "GUESS", "FORFEIT"]
    max_player_length = 10
    max_action_length = 7
    max_card_length = 9

    def __init__(self, player, action, target, card, claim, reason):
        self.player = player
        self.action = action
        self.target = target if target else ""
        self.card = card if card else "" 
        self.claim = claim if claim else ""
        self.reason = reason if reason else ""

    def rtrunc(self, s, width):
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
            claim = self.claim == "TRUE"
            guess_correct = (claim and self.card == self.claim) or (not claim and self.card != self.claim)
            if guess_correct:
                return f"{self.player} correctly guessed that {self.target} {"lied" if self.card != self.claim else "told the truth"} that the {self.card} was a {self.claim}."
            else:
                return f"{self.player} incorrectly thought that {self.target} was lying when claiming that the {self.card} was {"really a" if self.card == self.claim else "a"} {self.claim}. The claim was in fact {"true" if self.card == self.claim else "false"}."


    def __repr__(self):
        # Full representation of an action. Intended to be used for logging.
        return " ".join(
            self.rtrunc(self.player, self.max_player_length),
            self.rtrunc(self.action, self.max_action_length),
            self.rtrunc(self.target, self.max_player_length),
            self.rtrunc(self.card, self.max_card_length),
            self.rtrunc(self.claim, self.max_card_length),
            self.reason
        )


class Runner:
    types = ["COCKROACH", "BAT", "FLY", "FROG", "RAT", "SCORPION", "SPIDER", "STINKBUG"]
    deck = types * 8

    def __init__(self, player_names):
        self.players = {name: LlmPlayer(name) for name in player_names}  # map of player names -> Player objects.
        self.set_up_game()

    def chunk_cards_equally(self):
        # Generator to yield equally-sized chunks of a deck.
        k, m = divmod(len(self.deck), len(self.players))
        for i in range(len(self.players)):
            yield self.deck[i*k+min(i, m):(i+1)*k+min(i+1, m)]

    def set_up_game(self):
        # Set up a new game by dealing out cards and picking a player to start.
        random.shuffle(self.deck)  # shuffle deck in-place.
        self.player_hands = {player: Counter(chunk) for (player, chunk) in zip(self.players.keys(), self.chunk_cards_equally())}  # map of player names -> player cards (hidden).
        self.player_revealed = {player: Counter() for player in self.players.keys()}  # map of player names -> table cards (revealed).
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
        print(self.current_player + " says: '" + response.get("reason", "[No reason given]") + "'")
        return response

    def play_move(self, valid_targets, history):
        if len(valid_targets) == len(self.players) - 1:  # first move of the round. Must attack.
            instructions = "\n".join([
                f"You must play one of the cards from your hand: {self.get_enumerated_cards(self.player_hands[self.current_player])}.",
                f"You can target the following players: {", ".join(valid_targets)}."
                f"You can claim your card is any one of the following: {self.types}.",
                "Return a raw JSON object as a string with the keys 'card' (only the card you want to play, do not include the '1x', '2x', or '3x' count), 'target' (the player you want to pass to), 'claim' (the bug you claim your card is), and 'reason' (the reason why you chose this move)."
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
                return Move(self.current_player, "PLAY", response["target"], response["card"], response["claim"], response["reason"])
            except Exception as e:
                print(e, traceback.format_exc())
                return Move(self.current_player, "FORFEIT", None, None, None, f"Error parsing response: {e}")
        elif len(valid_targets) == 0:  # forced last move of the round. Must guess.
            last_move = history[-1]
            instructions = "\n".join([
                f"{last_move.target} passed a card to you and claimed it was a {last_move.claim}. You must determine whether this claim is TRUE or FALSE.",
                "Return a raw JSON object as a string with the keys 'claim' (either TRUE or FALSE), and 'reason' (the reason why you think so)."
            ])
            required_keys = ["claim", "reason"]
            try:
                response = self.get_response_from_current_player(instructions, required_keys)
                for key in ["claim", "reason"]:
                    if key not in response:
                        raise ValueError(f"Missing key '{key}' in response.")
                if type(response["claim"]) == bool:  # cast bool to string in case it was sent as a bool.
                    response["claim"] = "TRUE" if response["claim"] else "FALSE"
                if type(response["claim"]) != str:  # check if claim is a string.
                    raise ValueError(f"Claim must be a string.")
                response["claim"] = response["claim"].upper()
                if response["claim"] not in ["TRUE", "FALSE"]:
                    raise ValueError(f"Claim must be either TRUE or FALSE.")
                return Move(self.current_player, "GUESS", last_move.player, last_move.card, last_move.claim, response["reason"])
            except Exception as e:
                print(e, traceback.format_exc())
                return Move(self.current_player, "FORFEIT", None, last_move.card, None, f"Error parsing response: {e}")
        elif history[-1].action == "LOOK":  # looked at card last round, must pass.
            last_move = history[-1]
            instructions = "\n".join([
                f"You looked at the card that {last_move.target} passed to you and claimed it was a {last_move.claim}. It {'really is' if last_move.claim == last_move.card else 'is actually'} a {last_move.card}.",
                f"You need to pass the card to another player. You can pass to the following players: {", ".join(valid_targets)}."
                f"You can claim your card is any one of the following: {self.types}.",
                f"But remember, {last_move.target} claimed the card was a {last_move.claim}.",
                "Return a raw JSON object as a string with the keys 'target' (the player you want to pass to), 'claim' (what you claim your card is), and 'reason' (the reason why you chose this move)."
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
                return Move(self.current_player, "PASS", response["target"], last_move.card, response["claim"], response["reason"])
            except Exception as e:
                print(e, traceback.format_exc())
                return Move(self.current_player, "FORFEIT", None, last_move.card, None, f"Error parsing response: {e}")
        else:  # can decide whether to LOOK at card or GUESS.
            last_move = history[-1]
            instructions = "\n".join([
                f"{last_move.target} passed a card to you and claimed it was a {last_move.claim}. You can either LOOK at the card and pass it to another player, or try to GUESS whether this claim is TRUE or FALSE.",
                "If you want to LOOK at the card and pass it to another player, return a raw JSON object as a string with the keys 'action' (set to 'LOOK'), 'claim' (set to 'NONE') and 'reason' (the reason why you want to look and pass the card.",
                "If you want to GUESS whether this claim is TRUE or FALSE, return a raw JSON object as a string with the keys 'action' (set to 'GUESS'), 'claim' (either TRUE or FALSE), and 'reason' (the reason why you think so).",
            ])
            required_keys = ["action", "claim", "reason"]
            try:
                response = self.get_response_from_current_player(instructions, required_keys)
                if "action" in response and response["action"] == "LOOK":  # chose to LOOK.
                    return Move(self.current_player, "LOOK", last_move.player, last_move.card, None, response["reason"])
                else:  # chose to GUESS.
                    for key in ["claim", "reason"]:
                        if key not in response:
                            raise ValueError(f"Missing key '{key}' in response.")
                    if type(response["claim"]) == bool:  # cast bool to string in case it was sent as a bool.
                        response["claim"] = "TRUE" if response["claim"] else "FALSE"
                    if type(response["claim"]) != str:  # check if claim is a string.
                        raise ValueError(f"Claim must be a string.")
                    response["claim"] = response["claim"].upper()
                    if response["claim"] not in ["TRUE", "FALSE"]:
                        raise ValueError(f"Claim must be either TRUE or FALSE.")
                    return Move(self.current_player, "GUESS", last_move.player, last_move.card, last_move.claim, response["reason"])
            except Exception as e:
                print(e, traceback.format_exc())
                return Move(self.current_player, "FORFEIT", None, last_move.card, None, f"Error parsing response: {e}")
            

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
                card = move.card  # the actual card.
                claim = history[-2].claim  # last player's claim.
                guess = move.claim == "TRUE"  # whether guesser thought claim was true or false.
                if (claim == card and guess) or (claim != card and not guess):  # guesser guessed correctly.
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
                print(f"Player {losing_player} loses: {losing_reason}!")
                print("Face-up cards:")  # print revealed cards.
                for player, revealed in self.player_revealed.items():
                    print(f"  {player} has: {self.get_enumerated_cards(revealed)}.")
                break

            # Otherwise, play a round.
            print(f"New round, {self.current_player} goes first.")
            print(f"Player {self.current_player} hand: {self.get_enumerated_cards(self.player_hands[self.current_player])}.")
            round_loser, moves = self.play_round()
            losing_card = moves[-1].card
            print(f"{round_loser} lost that round and takes the {losing_card}.\n\n")
            history.extend(moves)


Runner(["llama3.1:8b", "gemma3:4b", "qwen2.5:7b"]).play_game()