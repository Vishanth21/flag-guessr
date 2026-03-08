import socket
import threading
import sys
import struct
import json
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout

console = Console(force_terminal=True) # wrap print with threads cuz user and 
print_lock = threading.Lock()           # server broadcast can happen at same time

HOST = "127.0.0.1"
PORT = 65432

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
    raw_data = recv_all(sock, msglen) #body
    if not raw_data:
        return None
    return json.loads(raw_data.decode('utf-8'))

def listen_to_server(client_socket):
    while True:
        try:
            response_dict = recv_msg(client_socket)
            with print_lock:
                if not response_dict:
                    console.print("\n[bold red]Server closed the connection.[/bold red]")
                    break
                
                # Clear the current prompt line first
                print("\r\033[K", end="", flush=True)

                if response_dict.get("type") == "STATUS":
                    console.print(f"[bold cyan]Server:[/bold cyan] {response_dict.get('message')}")
                elif response_dict.get("type") == "ECHO":
                    # Extract string inside the embedded dict if it's there
                    raw_echo = response_dict.get("server_received", {})
                    msg = raw_echo.get("message") if isinstance(raw_echo, dict) else str(raw_echo)
                    console.print(f"[bold cyan]Server (Echo):[/bold cyan] {msg}")
                else:
                    console.print(f"[bold cyan]Server JSON:[/bold cyan] {json.dumps(response_dict)}")
                
                # Re-draw the prompt safely
                console.print("[bold yellow]Say Something:[/bold yellow] ", end="")

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
    
    username = sys.argv[1]

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

        while True:
            try:
                data = input("Say Something: ")
                if not data.strip():
                    continue
                if data.lower() in ["quit", "exit"]:
                    break
                payload = {"type": "CHAT", "message": data}
                send_msg(client_socket, payload)
            except (EOFError, KeyboardInterrupt):
                break

if __name__ == "__main__":
    main()

    