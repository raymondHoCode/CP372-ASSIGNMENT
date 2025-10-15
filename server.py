#!/usr/bin/env python3
"""
CP372 - Computer Networks - Fall 2025
Server Program for Client-Server Chat Application
Authors: Raymond Ho, Sivaharan Janahan
Student IDs: 169065660, 169054638
"""

import os
import socket
import threading
from datetime import datetime

HOST = "0.0.0.0"            # listen on all interfaces
PORT = 5050                 # change if needed
MAX_CLIENTS = 3             # requirement: limit to 3 concurrent clients
REPO_DIR = "repo"           # server repository folder for files
BUF_SIZE = 4096
ENC = "utf-8"

# Ensure repo directory exists
os.makedirs(REPO_DIR, exist_ok=True)

# ---------- Shared State (Thread-Safe) ----------
clients_lock = threading.Lock()
client_counter = 0  # for Client01, Client02, Client03, ...
# Cache structure: { name: {addr, connected_at, disconnected_at, active} }
clients_cache = {}

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

def now_str():
    """Return current timestamp as formatted string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def current_active_count():
    """Return number of currently active (connected) clients."""
    with clients_lock:
        return sum(1 for v in clients_cache.values() if v["active"])

def add_client_record(name, addr):
    """Add a new client to the cache when they connect."""
    with clients_lock:
        clients_cache[name] = {
            "addr": f"{addr[0]}:{addr[1]}",
            "connected_at": now_str(),
            "disconnected_at": None,
            "active": True
        }

def close_client_record(name):
    """Mark a client as disconnected in the cache."""
    with clients_lock:
        if name in clients_cache:
            clients_cache[name]["active"] = False
            clients_cache[name]["disconnected_at"] = now_str()

def format_status():
    """Format the cache contents for the 'status' command."""
    with clients_lock:
        lines = []
        lines.append("=== Server Cache ===")
        if not clients_cache:
            lines.append("(no connections yet)")
        else:
            for name, info in clients_cache.items():
                status = "ACTIVE" if info["active"] else "DISCONNECTED"
                lines.append(
                    f"{name} [{status}] | addr={info['addr']} | "
                    f"connected={info['connected_at']} | "
                    f"disconnected={info['disconnected_at']}"
                )
        return "\n".join(lines)

def send_text(conn, text):
    """Send a text message to the client."""
    try:
        conn.sendall(text.encode(ENC))
    except Exception as e:
        print(f"[!] Error sending text: {e}")

def send_file(conn, filepath):
    """
    Send a file to the client with header format:
    FILESIZE <n>\nFILENAME <name>\n\n<binary data>
    """
    if not os.path.isfile(filepath):
        send_text(conn, "ERROR File not found\n")
        return
    
    try:
        size = os.path.getsize(filepath)
        name = os.path.basename(filepath)
        header = f"FILESIZE {size}\nFILENAME {name}\n\n"
        conn.sendall(header.encode(ENC))
        
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(BUF_SIZE)
                if not chunk:
                    break
                conn.sendall(chunk)
        print(f"[FILE] Sent {name} ({size} bytes)")
    except Exception as e:
        print(f"[!] Error sending file: {e}")

def handle_client(conn, addr, assigned_name):
    """Handle communication with a single client."""
    name = assigned_name
    reader = SocketReader(conn)
    
    try:
        # Send client name assignment
        send_text(conn, f"ASSIGNED {name}\n")
        
        # Receive name confirmation from client
        line = reader.readline()
        if line and line.startswith("NAME "):
            claimed = line.split(" ", 1)[1]
            name = claimed  # Use confirmed name

        # Add client to cache
        add_client_record(name, addr)
        print(f"[+] {name} connected from {addr}")

        # Send welcome message with available commands
        send_text(conn, f"HELLO {name}. Commands: status | list | get <file> | exit\n")

        # Main message loop
        while True:
            print(f"[{name}] DEBUG: Waiting for message...")
            msg = reader.readline()
            if not msg:  # Connection closed
                print(f"[{name}] DEBUG: Connection closed")
                break
                
            print(f"[{name}] DEBUG: Received message: '{msg}'")

            # Handle 'exit' command
            if msg == "exit":
                print(f"[{name}] DEBUG: Sending BYE")
                send_text(conn, "BYE\n")
                break

            # Handle 'status' command - show cache
            elif msg == "status":
                print(f"[{name}] DEBUG: Processing STATUS")
                status_msg = format_status()
                # Send each line separately and end with empty line
                for line in status_msg.split('\n'):
                    send_text(conn, line + "\n")
                send_text(conn, "\n")  # Empty line to mark end
                print(f"[{name}] DEBUG: Status sent")

            # Handle 'list' command - show repository files
            elif msg == "list":
                try:
                    files = sorted(os.listdir(REPO_DIR))
                    if files:
                        listing = "=== Available Files ===\n" + "\n".join(files)
                    else:
                        listing = "=== Available Files ===\n(repository is empty)"
                    send_text(conn, listing + "\n")
                except Exception as e:
                    send_text(conn, f"ERROR Cannot list files: {e}\n")

            # Handle 'get <filename>' command - send file
            elif msg.startswith("get "):
                parts = msg.split(maxsplit=1)
                if len(parts) < 2:
                    send_text(conn, "ERROR Usage: get <filename>\n")
                else:
                    filename = parts[1].strip()
                    filepath = os.path.join(REPO_DIR, filename)
                    send_file(conn, filepath)

            # Handle regular messages - echo with ACK
            else:
                send_text(conn, msg + " ACK\n")

    except Exception as e:
        print(f"[!] Error with {name} @ {addr}: {e}")
    finally:
        # Clean up connection
        try:
            conn.close()
        except:
            pass
        close_client_record(name)
        print(f"[-] {name} disconnected")

def main():
    """Main server function."""
    global client_counter
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        print(f"[SERVER] Listening on {HOST}:{PORT}")
        print(f"[SERVER] Repository directory: '{REPO_DIR}'")
        print(f"[SERVER] Max concurrent clients: {MAX_CLIENTS}")
        print("[SERVER] Press Ctrl+C to shut down")

        while True:
            conn, addr = server.accept()

            # Enforce maximum client limit
            if current_active_count() >= MAX_CLIENTS:
                print(f"[!] Connection rejected from {addr} (server at capacity)")
                try:
                    send_text(conn, "ERROR Server at capacity (max 3 clients). Try again later.\n")
                finally:
                    conn.close()
                continue

            # Assign next client name (Client01, Client02, etc.)
            client_counter += 1
            name = f"Client{client_counter:02d}"

            # Start new thread to handle this client
            t = threading.Thread(target=handle_client, args=(conn, addr, name), daemon=True)
            t.start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
    except Exception as e:
        print(f"[SERVER ERROR] {e}")