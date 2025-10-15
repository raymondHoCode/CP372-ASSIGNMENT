#!/usr/bin/env python3
"""
CP372 - Computer Networks - Fall 2025
Client Program for Client-Server Chat Application
Authors: Raymond Ho, Sivaharan Janahan
Student IDs: 169065660, 169054638
"""

import os
import socket
import sys

SERVER_HOST = "127.0.0.1"  # change to server IP if remote
SERVER_PORT = 5050
BUF_SIZE = 4096
ENC = "utf-8"

DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

class SocketReader:
    """Buffer for reading lines from socket."""
    def __init__(self, sock):
        self.sock = sock
        self.buffer = b""
    
    def readline(self):
        """Read a line from socket (until newline)."""
        while b"\n" not in self.buffer:
            data = self.sock.recv(BUF_SIZE)
            if not data:
                return None
            self.buffer += data
        
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line.decode(ENC)
    
    def read(self, n):
        """Read exactly n bytes."""
        while len(self.buffer) < n:
            data = self.sock.recv(BUF_SIZE)
            if not data:
                break
            self.buffer += data
        
        result = self.buffer[:n]
        self.buffer = self.buffer[n:]
        return result

def recv_file(reader, first_line):
    """
    Receive a file from server.
    File format: FILESIZE N\nFILENAME <name>\n\n<binary data>
    """
    try:
        parts = first_line.split()
        size = int(parts[1])
        
        fname_line = reader.readline()  # FILENAME <name>
        if not fname_line or not fname_line.startswith("FILENAME "):
            print("[ERROR] Invalid file header")
            return
            
        filename = fname_line.split(" ", 1)[1]
        blank = reader.readline()  # blank line after header

        out_path = os.path.join(DOWNLOADS_DIR, filename)
        
        with open(out_path, "wb") as f:
            remaining = size
            while remaining > 0:
                chunk = reader.read(min(BUF_SIZE, remaining))
                if not chunk:
                    break
                f.write(chunk)
                remaining -= len(chunk)
        
        print(f"[DOWNLOADED] {filename} -> {out_path} ({size} bytes)")
    except Exception as e:
        print(f"[ERROR] Receiving file failed: {e}")

def main():
    """Main client function."""
    host = SERVER_HOST
    port = SERVER_PORT
    
    # Allow command-line arguments for host and port
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        port = int(sys.argv[2])

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        reader = SocketReader(sock)

        # Receive client name assignment from server
        assigned = reader.readline()  # "ASSIGNED ClientXX"
        print(f"[DEBUG] Received assignment: '{assigned}'")
        if not assigned or not assigned.startswith("ASSIGNED "):
            print("[ERROR] Did not receive assignment from server.")
            sock.close()
            return
        
        name = assigned.split(" ", 1)[1]
        print(f"[INFO] Connected to server as {name}")
        
        # Confirm name to server
        sock.sendall(f"NAME {name}\n".encode(ENC))
        print(f"[DEBUG] Sent NAME confirmation")

        # Receive welcome message
        hello = reader.readline()
        print(f"[DEBUG] Received hello: '{hello}'")
        if hello:
            print(hello)

        # Main communication loop
        try:
            while True:
                user = input(f"{name}> ").strip()
                if not user:
                    continue
                
                # Send message to server
                print(f"[DEBUG] Sending: '{user}'")
                sock.sendall((user + "\n").encode(ENC))
                
                # Read server reply - could be text or file header
                print(f"[DEBUG] Waiting for response...")
                line = reader.readline()
                print(f"[DEBUG] Received: '{line}'")
                if line is None:
                    print("[INFO] Server closed connection.")
                    break

                # Handle file transfer
                if line.startswith("FILESIZE "):
                    recv_file(reader, line)
                    continue

                # Handle error messages
                if line.startswith("ERROR "):
                    print(line)
                    continue

                # Handle multi-line responses (status, list)
                if line.startswith("==="):
                    print(line)
                    # Read until empty line
                    while True:
                        next_line = reader.readline()
                        if not next_line or next_line.strip() == "":
                            break
                        print(next_line)
                    continue

                # Handle regular messages
                print(line)
                
                # Exit if user sent exit command
                if user.lower() == "exit":
                    break
                    
        except KeyboardInterrupt:
            try:
                sock.sendall(b"exit\n")
            except:
                pass
            print("\n[CLIENT] Exiting...")
        finally:
            sock.close()
                
    except ConnectionRefusedError:
        print(f"[ERROR] Cannot connect to server at {host}:{port}")
        print("[ERROR] Make sure the server is running.")
    except Exception as e:
        print(f"[ERROR] Connection error: {e}")

if __name__ == "__main__":
    main()