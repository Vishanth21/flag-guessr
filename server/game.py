from pathlib import Path
import json
import random
import time
import queue

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ansi_flags.json"

# Shared state for answer collection
answer_queue = queue.Queue()
scores = {}          # username -> total score
current_round = {}   # mutable dict holding round state so handle_client can check it


def _load_flags():
    """Load flag data from JSON file."""
    with open(DATA_PATH, "r") as fd:
        return json.load(fd)


def _build_question(flag_data, flag, question_id, timeout):
    """Build a QUESTION payload with 4 shuffled options."""
    distractors = [f for f in flag_data if f["country"] != flag["country"]]
    chosen = random.sample(distractors, 3)
    options = [f["country"] for f in chosen] + [flag["country"]]
    random.shuffle(options)

    return {
        "type": "QUESTION",
        "question_id": question_id,
        "time_limit": timeout,
        "flag_data": flag["ansi"],
        "options": options,
    }

def _score_answer(elapsed, timeout):
    """Calculate score: Base 10 + speed bonus (up to 5). time_taken is smaller for faster answers."""
    # max bonus of 5 if answered instantly, 0 if taken the whole timeout length
    elapsed = min(max(elapsed, 0), timeout)
    bonus = int(5 * ((timeout - elapsed) / timeout))
    return 10 + bonus


def _build_leaderboard():
    """Return a sorted LEADERBOARD payload."""
    rankings = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {
        "type": "LEADERBOARD",
        "rankings": [{"username": u, "score": s} for u, s in rankings],
    }


def _setup_new_game(rounds, clients_lock, connected_clients):
    """Initialize game state and select flags for the rounds."""
    global current_round
    
    flag_data = _load_flags()
    flags = random.sample(flag_data, min(rounds, len(flag_data)))

    # Initialise scores for every connected player
    with clients_lock:
        for username in connected_clients:
            scores.setdefault(username, 0)
            
    return flag_data, flags


def _clear_stale_answers():
    """Drain any leftover answers from the queue from previous rounds."""
    while not answer_queue.empty():
        try:
            answer_queue.get_nowait()
        except queue.Empty:
            break


def _evaluate_answer(ans, question_id, correct_country, round_start, timeout):
    """Process a single answer, check correctness, assign score, and generate evaluation message."""
    username = ans.get("username")
    ans_qid = ans.get("question_id")
    chosen = ans.get("answer")

    # Ignore stale / duplicate / wrong-round answers
    if ans_qid != question_id or username in current_round["answered"]:
        return None

    current_round["answered"].add(username)
    
    elapsed = time.time() - round_start

    earned = _score_answer(elapsed, timeout)
    if chosen == correct_country:
        scores[username] = scores.get(username, 0) + earned
        evaluation = {
            "result": "correct",
            "score_earned": earned,
            "message": f"Correct! +{earned} points ([green]{elapsed:.1f}s[/green])"
        }
    else:
        scores[username] = scores.get(username, 0) - earned
        evaluation = {
            "result": "wrong",
            "score_earned": -earned,
            "message": f"Wrong! The answer was {correct_country}. ([red]{elapsed:.1f}s[/red])"
        }
        
    return username, evaluation

def _collect_answers(question_id, correct_country, round_start, timeout, connected_clients):
    """Listen for answers from clients until the round timeout expires. Returns dict of evaluations."""
    deadline = round_start + timeout
    evaluations = {}
    
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
            
        try:
            ans = answer_queue.get(timeout=min(remaining, 0.5))
        except queue.Empty:
            continue

        result = _evaluate_answer(ans, question_id, correct_country, round_start, timeout)
        if not result:
            continue
            
        username, evaluation = result
        evaluations[username] = evaluation

        # break early if everyone answered
        if len(evaluations) == len(connected_clients):
            break

    return evaluations

def _play_round(i, flag, flag_data, flags, timeout, clients_lock, connected_clients, broadcast, send_msg):
    """Execute a single round of the game."""
    global current_round
    
    question_id = i
    correct_country = flag["country"]
    question = _build_question(flag_data, flag, question_id, timeout)

    # Update shared round state so server can route answers
    current_round.update({
        "active": True,
        "question_id": question_id,
        "correct": correct_country,
        "options": question["options"],
        "start_time": None,       # set after broadcast
        "answered": set(),        # usernames who already answered
    })

    _clear_stale_answers()
 
    # Broadcast question
    broadcast(question)
    round_start = time.time()
    current_round["start_time"] = round_start

    broadcast({
        "type": "STATUS",
        "message": f"[GAME] Round {i}/{len(flags)}: Guess the flag! You have {timeout}s.",
    })

    evaluations = _collect_answers(question_id, correct_country, round_start, timeout, connected_clients)

    # ── round over ──
    current_round["active"] = False

    # Send out the batched evaluations to each specific player
    with clients_lock:
        for username, sock in connected_clients.items():
            if username in evaluations:
                
                payload = evaluations[username].copy()
                payload["type"] = "EVALUATION"
                try:
                    send_msg(sock, payload)
                except OSError:
                    pass
            else:
                # Did not answer in time
                try:
                    send_msg(sock, {
                        "type": "EVALUATION",
                        "result": "timeout",
                        "score_earned": 0,
                        "message": f"Time's up! The answer was {correct_country}."
                    })
                except OSError:
                    pass


    # dont broadcast for last round, game-over broadcast will handle it
    # short pause between rounds
    if i < len(flags):
        broadcast(_build_leaderboard())
        broadcast({
            "type": "STATUS",
            "message": "[GAME] Next round in 5 seconds...",
        })
        time.sleep(5)

def reset_game(game_started):
    current_round.clear()
    scores.clear()
    game_started.clear()

def start(rounds, timeout, clients_lock, connected_clients, broadcast, send_msg, game_started):
    """Main game loop, called from the admin console thread.
    Takes server functions and state as arguments to avoid circular imports.
    """
    flag_data, flags = _setup_new_game(rounds, clients_lock, connected_clients)

    for i, flag in enumerate(flags, start=1):
        _play_round(i, flag, flag_data, flags, timeout, clients_lock, connected_clients, broadcast, send_msg)

    # game over
    broadcast({
        "type": "STATUS",
        "message": "[GAME] Game Over! Final standings:",
    })
    broadcast(_build_leaderboard())

    # Reset state for a new game
    reset_game(game_started)