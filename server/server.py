import socket
import threading

HOST = "127.0.0.1"
PORT = 65432

def handle_client(connection, addr):
    with connection:
        print(f"Client {addr} connected.")
        while True:
            try:
                data = connection.recv(2048)
                if not data:
                    print(f"Client {addr} disconnected cleanly.")
                    break

                message = data.decode("utf-8")
                print(f"[{addr[0]}:{addr[1]}] says: {message}")
                
                reply = f"Server received: {message}\n"
                connection.sendall(reply.encode("utf-8"))
            except ConnectionError:
                print(f"Client {addr} forcefully disconnected.")
                break

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # force reuse the socket
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"Server listening on {HOST}:{PORT}...")

        while True:
            client_socket, addr = server_socket.accept()
            client_thread = threading.Thread(
                target=handle_client, args=(client_socket, addr), daemon=True
            )
            client_thread.start()
            print(f"Active client threads: {threading.active_count() - 1}")

if __name__ == "__main__":
    main()

