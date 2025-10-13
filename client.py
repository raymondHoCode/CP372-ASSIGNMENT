#!/usr/bin/env python3
import os
import socket
import sys

SERVER_HOST = "127.0.0.1"  # change to server IP if remote
SERVER_PORT = 5050
BUF_SIZE = 4096
ENC = "utf-8"

DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def recv_line(sock_file):
    data = sock_file.readline()
    if not data:
        return None
    return data.decode(ENC).rstrip("\n")

def recv_file(sock_file, first_line):
    """We already read a line that starts with FILESIZE N"""
    try:
        parts = first_line.split()
        size = int(parts[1])
        fname_line = recv_line(sock_file)  # FILENAME <name>
        assert fname_line.startswith("FILENAME ")
        filename = fname_line.split(" ", 1)[1]
        blank = sock_file.readline()  # the blank line after header

        out_path = os.path.join(DOWNLOADS_DIR, filename)
        remaining = size
        with open(out_path, "wb") as f:
            while remaining > 0:
                chunk = sock_file.read(min(BUF_SIZE, remaining))
                if not chunk:
                    break
                f.write(chunk)
                remaining -= len(chunk)
        print(f"[DOWNLOADED] {filename} -> {out_path} ({size} bytes)")
    except Exception as e:
        print(f"[ERROR] Receiving file failed: {e}")

def main():
    host = SERVER_HOST
    port = SERVER_PORT
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        port = int(sys.argv[2])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        sf = s.makefile("rwb", buffering=0)

        # Receive assignment and confirm name
        assigned = recv_line(sf)  # "ASSIGNED ClientXX"
        if not assigned or not assigned.startswith("ASSIGNED "):
            print("[ERROR] Did not receive assignment from server.")
            return
        name = assigned.split(" ", 1)[1]
        sf.write(f"NAME {name}\n".encode(ENC))

        hello = recv_line(sf)
        if hello:
            print(hello)

        try:
            while True:
                user = input("> ").strip()
                if not user:
                    continue
                sf.write((user + "\n").encode(ENC))
                # Read server reply. Could be text or file header.
                line = recv_line(sf)
                if line is None:
                    print("[INFO] Server closed connection.")
                    break

                if line.startswith("FILESIZE "):
                    recv_file(sf, line)
                    continue

                if line.startswith("ERROR "):
                    print(line)
                    continue

                print(line)
                if user.lower() == "exit":
                    break
        except KeyboardInterrupt:
            try:
                sf.write(b"exit\n")
            except:
                pass
            print("\n[CLIENT] Exiting…")

if __name__ == "__main__":
    main()
