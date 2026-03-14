import socket
import threading
import sys
import struct
import json
import time
import readline
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console(force_terminal=True)
print_lock = threading.Lock()

HOST = "127.0.0.1"
PORT = 65432

# Game state
game_active = threading.Event()
can_answer = threading.Event()
current_question = {}
previous_scores = {}
round_end_time = 0.0


def recv_all(sock, n):
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


def send_msg(sock, msg_dict):
    msg_bytes = json.dumps(msg_dict).encode('utf-8')
    header = struct.pack('>I', len(msg_bytes))
    sock.sendall(header + msg_bytes)

def recv_msg(sock):
    raw_msglen = recv_all(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    raw_data = recv_all(sock, msglen)
    if not raw_data:
        return None
    return json.loads(raw_data.decode('utf-8'))


def _render_leaderboard(rankings):
    table = Table(title="Leaderboard", show_lines=True)
    table.add_column("Rank", style="bold", justify="center")
    table.add_column("Player", style="cyan")
    table.add_column("Score", style="white", justify="right")
    for idx, entry in enumerate(rankings, start=1):
        username = entry["username"]
        score = entry["score"]
        
        # Calculate diff
        prev_score = previous_scores.get(username, 0)
        diff = score - prev_score
        previous_scores[username] = score
        
        if diff > 0:
            diff_str = f"[green](+{diff})[/green]"
        elif diff < 0:
            diff_str = f"[red]({diff})[/red]"
        else:
            diff_str = f"[dim](+0)[/dim]"
            
        score_display = f"{score} {diff_str}"
        table.add_row(str(idx), username, score_display)
    return table


def _timer_thread():
    while True:
        try:
            can_answer.wait()
            while can_answer.is_set():
                remaining = max(0.0, round_end_time - time.time())
                
                with print_lock:
                    # Only re-draw if we are still active and it's our prompt
                    if can_answer.is_set():
                        buf = readline.get_line_buffer() if readline else ""
                        sys.stdout.write("\r\x1b[K")
                        console.print(f"[bold yellow]Your answer (1-4)[/bold yellow] [cyan]({remaining:.3f}s)[/cyan]: {buf}", end="")
                        sys.stdout.flush()
                
                if remaining <= 0:
                    break
                time.sleep(0.05)
        except Exception:
            break


def listen_to_server(client_socket):
    while True:
        try:
            response_dict = recv_msg(client_socket)
            with print_lock:
                if not response_dict:
                    console.print("\n[bold red]Server closed the connection.[/bold red]")
                    break

                # Clear the current prompt line
                print("\r\033[K", end="", flush=True)

                msg_type = response_dict.get("type")

                if msg_type == "QUESTION":
                    global round_end_time
                    time_limit = response_dict["time_limit"]
                    round_end_time = time.time() + time_limit
                    
                    game_active.set()
                    can_answer.set()
                    current_question["question_id"] = response_dict["question_id"]
                    current_question["options"] = response_dict["options"]
                    current_question["time_limit"] = time_limit

                    # Build the question display
                    flag_art = response_dict.get("flag_data", "")
                    ansi_text = Text.from_ansi(flag_art)
                    
                    options = response_dict["options"]
                    options_text = "\n".join(
                        f"  [bold yellow]{i}.[/bold yellow] {opt}"
                        for i, opt in enumerate(options, start=1)
                    )
                    
                    # Combine ansi string object and normal markup string into a group
                    content = Group(ansi_text, "", options_text)
                    
                    panel = Panel(
                        content,
                        title=f"[bold]Round {response_dict['question_id']}[/bold]",
                        subtitle=f"⏱  {time_limit}s",
                        border_style="bright_blue",
                        expand=False,
                    )
                    console.print(panel)
                    console.print("[bold yellow]Your answer (1-4):[/bold yellow] ", end="")

                elif msg_type == "EVALUATION":
                    result = response_dict.get("result")
                    message = response_dict.get("message", "")
                    if result == "correct":
                        console.print(f"[bold green]{message}[/bold green]")
                    else:
                        console.print(f"[bold red]{message}[/bold red]")

                elif msg_type == "LEADERBOARD":
                    game_active.clear()
                    can_answer.clear()
                    current_question.clear()
                    rankings = response_dict.get("rankings", [])
                    table = _render_leaderboard(rankings)
                    console.print(table)

                elif msg_type == "STATUS":
                    console.print(f"[bold cyan]Server:[/bold cyan] {response_dict.get('message')}")
                else:
                    console.print(f"[bold cyan]Server JSON:[/bold cyan] {json.dumps(response_dict)}")

        except OSError:
            with print_lock:
                console.print("\n[bold red]Connection to server lost.[/bold red]")
            break

    client_socket.close()
    sys.exit(0)


def main():
    if len(sys.argv) < 2:
        console.print("[bold red]Usage: python client.py <username>[/bold red]")
        sys.exit(1)

    username = sys.argv[1].strip()
    if not username:
        console.print("[bold red]Usage: python client.py <username>[/bold red]")
        sys.exit(1)
    
    timer_t = threading.Thread(target=_timer_thread, daemon=True)
    timer_t.start()
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        try:
            client_socket.connect((HOST, PORT))
        except ConnectionRefusedError:
            console.print(f"[bold red]Connection failed.[/bold red] Is the server running on {HOST}:{PORT}?")
            return

        console.print(f"[bold green]Connected to server at {HOST}:{PORT}[/bold green]")

        # send initial JOIN message with username
        join_payload = {"type": "JOIN", "username": username}
        send_msg(client_socket, join_payload)

        listener_thread = threading.Thread(target=listen_to_server, args=(client_socket,), daemon=True)
        listener_thread.start()
        console.print("[dim]Waiting for game to start...[/dim]")

        while True:
            try:
                # Block until a question is active and user hasn't answered
                can_answer.wait()

                # read buffer -> clear prompt line -> print new prompt with buffer (refer timer thread)
                data = input()

                # Send an ANSWER if still in an active round
                if can_answer.is_set() and data.strip() in ["1", "2", "3", "4"]:
                    choice_idx = int(data.strip()) - 1
                    options = current_question.get("options", [])
                    if 0 <= choice_idx < len(options):
                        payload = {
                            "type": "ANSWER",
                            "question_id": current_question.get("question_id"),
                            "answer": options[choice_idx],
                            "client_elapsed_time": time.time() - (round_end_time - current_question.get("time_limit", 10.0))
                        }
                        send_msg(client_socket, payload)
                        can_answer.clear()
                        console.print("[dim]Answer sent. Waiting for others...[/dim]")
                    else:
                        console.print("[bold red]Invalid option.[/bold red]")
            except (EOFError, KeyboardInterrupt):
                break

if __name__ == "__main__":
    main()