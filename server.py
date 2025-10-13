#!/usr/bin/env python3
import os
import socket
import threading
import time
from datetime import datetime

HOST = "0.0.0.0"            # listen on all interfaces
PORT = 5050                 # change if needed
MAX_CLIENTS = 3             # requirement: limit to 3
REPO_DIR = "repo"           # server repository folder for files
BUF_SIZE = 4096
ENC = "utf-8"

# Ensure repo exists
os.makedirs(REPO_DIR, exist_ok=True)

# ---------- Shared state ----------
clients_lock = threading.Lock()
client_counter = 0  # for Client01, Client02, ...
# cache: name -> dict(...)
clients_cache = {}  # { name: {addr, connected_at, disconnected_at, active} }

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def current_active_count():
    with clients_lock:
        return sum(1 for v in clients_cache.values() if v["active"])

def add_client_record(name, addr):
    with clients_lock:
        clients_cache[name] = {
            "addr": f"{addr[0]}:{addr[1]}",
            "connected_at": now_str(),
            "disconnected_at": None,
            "active": True
        }

def close_client_record(name):
    with clients_lock:
        if name in clients_cache:
            clients_cache[name]["active"] = False
            clients_cache[name]["disconnected_at"] = now_str()

def format_status():
    with clients_lock:
        lines = []
        lines.append("=== Server Cache ===")
        for name, info in clients_cache.items():
            lines.append(
                f"{name} | addr={info['addr']} | "
                f"connected={info['connected_at']} | "
                f"disconnected={info['disconnected_at']}"
            )
        if len(lines) == 1:
            lines.append("(no connections yet)")
        return "\n".join(lines) + "\n"

def send_text(conn, text):
    conn.sendall(text.encode(ENC))

def send_file(conn, filepath):
    """Send file with a tiny header:
       FILESIZE <n>\nFILENAME <name>\n\n<bytes...>
    """
    if not os.path.isfile(filepath):
        send_text(conn, "ERROR File not found\n")
        return
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

def handle_client(conn, addr, assigned_name):
    name = assigned_name
    try:
        # Ask client to confirm (client will send: NAME <name>)
        send_text(conn, f"ASSIGNED {name}\n")
        # Read a single line for the name confirmation
        conn_file = conn.makefile("rwb", buffering=0)
        line = conn_file.readline().decode(ENC).strip()
        if line.startswith("NAME "):
            claimed = line.split(" ", 1)[1]
            # Optional: verify matches assigned
            name = claimed

        add_client_record(name, addr)
        print(f"[+] {name} connected from {addr}")

        send_text(conn, f"HELLO {name}. Commands: status | list | get <file> | exit\n")

        while True:
            line = conn_file.readline()
            if not line:
                break
            msg = line.decode(ENC).strip()

            if msg.lower() == "exit":
                send_text(conn, "BYE\n")
                break

            elif msg.lower() == "status":
                send_text(conn, format_status())

            elif msg.lower() == "list":
                files = sorted(os.listdir(REPO_DIR))
                listing = "\n".join(files) if files else "(empty)"
                send_text(conn, listing + "\n")

            elif msg.lower().startswith("get "):
                _, filename = msg.split(" ", 1)
                filepath = os.path.join(REPO_DIR, filename)
                send_file(conn, filepath)

            else:
                # If user typed only a filename (no "get "), try to send it.
                candidate = os.path.join(REPO_DIR, msg)
                if os.path.isfile(candidate):
                    send_file(conn, candidate)
                else:
                    send_text(conn, msg + " ACK\n")

    except Exception as e:
        print(f"[!] Error with {name} @ {addr}: {e}")
    finally:
        try:
            conn.close()
        except:
            pass
        close_client_record(name)
        print(f"[-] {name} disconnected")

def main():
    global client_counter
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        print(f"[SERVER] Listening on {HOST}:{PORT}, repo='{REPO_DIR}'")

        while True:
            conn, addr = server.accept()

            # Enforce max clients
            if current_active_count() >= MAX_CLIENTS:
                try:
                    send_text(conn, "BUSY Server at capacity (3). Try later.\n")
                finally:
                    conn.close()
                continue

            # Assign next client name
            client_counter += 1
            name = f"Client{client_counter:02d}"

            t = threading.Thread(target=handle_client, args=(conn, addr, name), daemon=True)
            t.start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down…")
