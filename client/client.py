import socket
import threading
import sys

HOST = "127.0.0.1"
PORT = 65432

def listen_to_server(client_socket):
    while True:
        try:
            response = client_socket.recv(1024)
            if not response:
                print("\nServer closed the connection.")
                break
            print(f"\r{response.decode('utf-8')}", end="")
            print("\rSay Something: ", end="", flush=True)
        except ConnectionError:
            print("\nConnection to server lost.")
            break
    
    client_socket.close()
    sys.exit(0)

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        try:
            client_socket.connect((HOST, PORT))
        except ConnectionRefusedError:
            print(f"Connection failed. Is the server running on {HOST}:{PORT}?")
            return

        print(f"Connected to server at {HOST}:{PORT}")

        listener_thread = threading.Thread(target=listen_to_server, args=(client_socket,), daemon=True)
        listener_thread.start()

        while True:
            try:
                data = input("Say Something: ")
                if not data.strip():
                    continue
                if data.lower() in ["quit", "exit"]:
                    break
                client_socket.sendall(data.encode("utf-8"))
            except (EOFError, KeyboardInterrupt):
                break

if __name__ == "__main__":
    main()

    