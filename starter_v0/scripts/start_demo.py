from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(tempfile.gettempdir()) / "ProblemSolver-demo"
DOWNLOAD = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"


def cloudflared_binary() -> str:
    installed = shutil.which("cloudflared")
    if installed:
        return installed
    if sys.platform != "win32":
        raise RuntimeError("Install cloudflared first, or use --local-only.")
    target = RUNTIME / "cloudflared.exe"
    if not target.exists() or target.stat().st_size < 1_000_000:
        print("Downloading the official Cloudflare Windows binary...", flush=True)
        with urllib.request.urlopen(DOWNLOAD, timeout=60) as response:
            content = response.read()
        if not content.startswith(b"MZ") or len(content) < 1_000_000:
            raise RuntimeError("Cloudflare download was not a Windows executable.")
        target.write_bytes(content)
    return str(target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the Streamlit demo and optional public Cloudflare link.")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", args.port)) == 0:
            raise SystemExit(f"Port {args.port} is already in use. Choose --port with another value.")

    local_url = f"http://127.0.0.1:{args.port}"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    tunnel = None
    deployment_path = ROOT / "artifacts" / "deployment.json"
    deployment = {
        "local_url": local_url,
        "public_url": None,
        "hosting": "Cloudflare Quick Tunnel" if not args.local_only else "local",
        "temporary": True,
        "active": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    with (RUNTIME / "streamlit.log").open("wb") as server_log:
        server = subprocess.Popen([
            sys.executable, "-X", "utf8", "-m", "streamlit", "run", str(ROOT / "app.py"),
            "--server.address", "127.0.0.1", "--server.port", str(args.port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false",
        ], cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT, creationflags=flags)
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError(f"Streamlit stopped; check {RUNTIME / 'streamlit.log'}")
                try:
                    with urllib.request.urlopen(f"{local_url}/_stcore/health", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.5)
            else:
                raise RuntimeError("Streamlit did not become ready within 45 seconds.")
            deployment["active"] = True
            deployment_path.write_text(json.dumps(deployment, indent=2), encoding="utf-8")
            print(f"LOCAL_URL={local_url}", flush=True)
            if args.local_only:
                print("Local demo is running. Press Ctrl+C to stop.", flush=True)
                server.wait()
            else:
                tunnel = subprocess.Popen([
                    cloudflared_binary(), "tunnel", "--url", local_url,
                    "--protocol", "quic", "--edge-ip-version", "4", "--no-autoupdate",
                ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", creationflags=flags)
                assert tunnel.stdout is not None
                for line in tunnel.stdout:
                    print(line.rstrip(), flush=True)
                    matches = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                    for public_url in matches:
                        if public_url == "https://api.trycloudflare.com":
                            continue
                        deployment["public_url"] = public_url
                        deployment_path.write_text(json.dumps(deployment, indent=2), encoding="utf-8")
                raise RuntimeError("Cloudflare tunnel stopped. Restart to obtain a new public link.")
        except KeyboardInterrupt:
            print("Stopping the demo...", flush=True)
        finally:
            for process in (tunnel, server):
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
            deployment["active"] = False
            deployment["stopped_at"] = datetime.now(timezone.utc).isoformat()
            deployment_path.write_text(json.dumps(deployment, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
