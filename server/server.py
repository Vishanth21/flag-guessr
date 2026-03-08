import socket
import threading
import struct
import json

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
            print(f"Player '{username}' connected from {addr[0]}:{addr[1]}.")

            # send welcome guidelines
            guidelines = (
                f"Welcome to Flag-Guessr, {username}!\n"
                "You will see an flag and have x seconds to guess the country.\n"
                "Wait for game to start.\n"
            )
            send_msg(connection, {"type": "STATUS", "message": guidelines})

            while True:
                data = recv_msg(connection)
                if not data:
                    print(f"Player '{username}' disconnected cleanly.")
                    break

                print(f"[{username}] says: {data}")
                reply = {"type": "ECHO", "server_received": data}
                send_msg(connection, reply)

        except ConnectionError:
            print(f"Player '{username or f'{addr[0]}:{addr[1]}'}' forcefully disconnected.")

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

