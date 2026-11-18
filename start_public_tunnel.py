"""Start a Cloudflare Public Tunnel for the GeoSketch FastAPI backend.

This exposes the local backend (http://127.0.0.1:8000) to the public internet
via a secure HTTPS URL (https://xxxx.trycloudflare.com).
It automatically updates `config.h` so the ESP32 can connect over ANY Wi-Fi network.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CLOUDFLARED_EXE = os.path.join(ROOT_DIR, "tools", "cloudflared.exe")
CONFIG_H_PATHS = [
    os.path.join(ROOT_DIR, "firmware", "geosketch_esp32c3", "config.h"),
    os.path.join(r"D:\Projects\GeoSketch", "firmware", "geosketch_esp32c3", "config.h"),
]


def update_config_h(public_url: str) -> None:
    for path in CONFIG_H_PATHS:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = re.sub(
                r'#define\s+GEOSKETCH_API_BASE_URL\s+"[^"]+"',
                f'#define GEOSKETCH_API_BASE_URL    "{public_url}"',
                content,
            )
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"[OK] Updated GEOSKETCH_API_BASE_URL in: {path}")
        except Exception as e:
            print(f"[!] Warning: Could not update {path}: {e}")


def main() -> None:
    if not os.path.exists(CLOUDFLARED_EXE):
        print(f"Error: {CLOUDFLARED_EXE} not found.")
        sys.exit(1)

    print("=================================================================")
    print(" GeoSketch - Starting Cloudflare Public Internet Tunnel")
    print(" Tunneling: http://127.0.0.1:8000 -> https://*.trycloudflare.com")
    print("=================================================================")

    proc = subprocess.Popen(
        [
            CLOUDFLARED_EXE,
            "tunnel",
            "--protocol",
            "http2",
            "--edge-ip-version",
            "4",
            "--url",
            "http://127.0.0.1:8000",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    public_url = None
    start_time = time.time()

    try:
        while time.time() - start_time < 30:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    print("Error: Cloudflare tunnel process exited unexpectedly.")
                    break
                time.sleep(0.1)
                continue

            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match:
                public_url = match.group(0)
                break

        if not public_url:
            print("Failed to obtain public URL within 30 seconds.")
            proc.terminate()
            sys.exit(1)

        print()
        print("*****************************************************************")
        print("  PUBLIC TUNNEL ONLINE!")
        print(f"  Public Backend URL : {public_url}")
        print("*****************************************************************")
        print("-> Automatically updated GEOSKETCH_API_BASE_URL in config.h!")
        print("-> The ESP32 and your laptop DO NOT need to be on the same network.")
        print("-> You can now connect the ESP32 to ANY Wi-Fi network anywhere.")
        print("-> Keep this terminal OPEN while using the tracker.", flush=True)
        print("*****************************************************************", flush=True)
        print(flush=True)

        update_config_h(public_url)

        # Stream remaining logs until interrupted
        while True:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    print(f"[!] cloudflared exited with code {proc.returncode}", flush=True)
                    break
                time.sleep(0.5)
                continue
            low = line.lower()
            if any(k in low for k in ("err", "warn", "unregister", "disconnect", "registered")):
                print(line.strip(), flush=True)

    except KeyboardInterrupt:
        print("\nStopping tunnel...")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Tunnel closed.")


if __name__ == "__main__":
    main()
