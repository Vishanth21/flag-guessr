import socket
import threading
import struct
import json
import game
import ssl
import os
import sys 

HOST = "127.0.0.1"
PORT = 65432

# Path to certificates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERT_PATH = os.path.join(BASE_DIR, "certs", "server.crt")
KEY_PATH = os.path.join(BASE_DIR, "certs", "server.key")

connected_clients = {}
clients_lock = threading.Lock()
game_started = threading.Event()
context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)

def broadcast(msg_dict):
    # broadcast a message to every client 
    with clients_lock:
        clients_copy = list(connected_clients.values())
    
    for client_socket in clients_copy:
        try:
            send_msg(client_socket, msg_dict)
        except OSError:
            pass

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


# extract message header first, then extract message body
def recv_msg(sock):
    raw_msglen = recv_all(sock, 4) #header
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    
    # 1. Payload Size Validation (prevent huge headers)
    if msglen > 4096:
        print(f"Security: Connection dropped. Claimed payload size ({msglen} bytes) too large.")
        return None
        
    # 2. Body Read Timeout (prevent slow-loris attack)
    old_timeout = sock.gettimeout()
    sock.settimeout(5.0)
    try:
        raw_data = recv_all(sock, msglen) #body
    except socket.timeout:
        print("Security: Connection dropped. Timed out receiving message body.")
        return None
    finally:
        sock.settimeout(old_timeout)
        
    if not raw_data:
        return None
    return json.loads(raw_data.decode('utf-8'))

def handle_client(connection, addr):
    username = None
    with connection:
        try:
            # wait for the initial JOIN message
            join_data = recv_msg(connection)
            if not join_data or join_data.get("type") != "JOIN":
                print(f"[{addr[0]}:{addr[1]}] Failed to join properly.")
                return

            username = join_data.get("username", "Unknown")

            with clients_lock:
                if username in connected_clients:
                    send_msg(connection, {"type": "ERROR", "message": f"Username {username} already taken."})
                    return
                
                connected_clients[username] = connection
                player_count = len(connected_clients)
                print(f"Player '{username}' connected from {addr[0]}:{addr[1]}.")
                print(f"Active connections: {player_count}")

            send_msg(connection, {"type": "STATUS", "message": f"Welcome to Flag-Guessr, {username}!\n"})

            broadcast({"type": "STATUS", "message": f"[LOBBY] '{username}' joined. ({player_count} players ready)"})

            while True:
                data = recv_msg(connection)
                if not data:
                    print(f"Player '{username}' disconnected cleanly.")
                    break

                msg_type = data.get("type")

                if msg_type == "ANSWER" and game_started.is_set():
                    # only accept answers for the active round
                    active_qid = game.current_round.get("question_id")
                    if data.get("question_id") == active_qid:
                        data["username"] = username
                        game.answer_queue.put(data)
                else:
                    print(f"[{username}] unknown message: {data}")

        except OSError:
            print(f"Player '{username or f'{addr[0]}:{addr[1]}'}' forcefully disconnected.")
        finally:
            with clients_lock:
                was_connected = False
                if username and username in connected_clients:
                    del connected_clients[username]
                    was_connected = True
                player_count = len(connected_clients)
            
            if was_connected:
                broadcast({"type": "STATUS", "message": f"[LOBBY] '{username}' left. ({player_count} players ready)"})

def admin_console():
    """Listens for the 'start <rounds> <timeout>' command from the server operator."""
    while True:
        try:
            cmd = input().strip()
            if not cmd:
                continue
            parts = cmd.split()
            if parts[0].lower() == "reset":
                game.reset_game(game_started)
                print("Game was reset successfully.")
                continue
            if parts[0].lower() != "start":
                print("Unknown command. Usage: start <rounds> <timeout>")
                continue
            if game_started.is_set():
                print("A game is already in progress.")
                continue
            try:
                rounds, timeout = int(parts[1]), int(parts[2])
            except (IndexError, ValueError):
                print("Usage: start <rounds> <timeout>")
                continue
            with clients_lock:
                player_count = len(connected_clients)
            if player_count == 0:
                print("Cannot start game: 0 players connected.")
            else:
                print(f"Starting game of {rounds} rounds, {timeout}s timeout with {player_count} players...")
                game_started.set()
                broadcast({"type": "STATUS", "message": "[LOBBY] Admin started the game! Prepare yourselves."})
                game_thread = threading.Thread(
                    target=game.start, args=(
                        rounds, timeout, clients_lock, connected_clients, broadcast, send_msg, game_started
                    ), daemon=True
                )
                game_thread.start()
        except (EOFError, KeyboardInterrupt):
            break

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # force reuse the socket
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        server_socket.settimeout(1.0) # wake up every 1s to check for other inputs(keyboard interrupt specifically) than socket.accept() sicne its blocking
        print(f"Server listening on {HOST}:{PORT}... Type 'start' to begin the game.")

        # start listening to server admin input
        admin_thread = threading.Thread(target=admin_console, daemon=True)
        admin_thread.start()

        while True:
            try:
                client_socket, addr = server_socket.accept()
                try:
                    secure_socket = context.wrap_socket(client_socket, server_side=True) 
                    client_thread = threading.Thread(
                        target=handle_client, args=(secure_socket, addr), daemon=True
                    )
                    client_thread.start()
                    
                except (ssl.SSLError, OSError) as e:
                    print(f"SSL handshake or connection error: {e}")
                    client_socket.close()
            except socket.timeout:
                continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("KeyboardInterrupt: Shutting down gracefully...")
        with clients_lock:
            for sock in connected_clients.values():
                try:
                    sock.close()
                except: pass
        sys.exit(0)
