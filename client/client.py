import socket
import threading
import sys
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

def listen_to_server(client_socket):
    while True:
        try:
            response_dict = recv_msg(client_socket)
            if not response_dict:
                print("\nServer closed the connection.")
                break
            print(f"\r[Server]: {json.dumps(response_dict)}")
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
                payload = {"type": "CHAT", "message": data}
                send_msg(client_socket, payload)
            except (EOFError, KeyboardInterrupt):
                break

if __name__ == "__main__":
    main()

    