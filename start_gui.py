#!/usr/bin/env python3
"""
SCAFAD GUI Launcher — one-command startup for examiners.

This script:
  1. Verifies Python and GUI build artefacts
  2. Spawns the FastAPI backend (uvicorn) on 127.0.0.1:8088 in the background
  3. Spawns the static-file + reverse-proxy server (gui_server.py) on
     127.0.0.1:8765 in the foreground
  4. Tears both down on Ctrl+C
"""

from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
GUI_DIR   = REPO_ROOT / "scafad" / "gui"

BACKEND_HOST  = "127.0.0.1"
BACKEND_PORT  = 8088
FRONTEND_PORT = 8765
BACKEND_BOOT_TIMEOUT = 25  # seconds


# ──────────────────────────────────────────────────────────────────────
#  Environment checks
# ──────────────────────────────────────────────────────────────────────

def verify_python_version() -> None:
    if sys.version_info < (3, 9):
        print("❌ Error: Python 3.9+ required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✓ Python {sys.version.split()[0]} detected")


def verify_gui_files() -> None:
    required = {
        "gui_server.py":            "Python static-file server",
        "frontend/dist/index.html": "React GUI build artefact",
        "backend/main.py":          "FastAPI backend entrypoint",
    }
    missing = []
    for rel, desc in required.items():
        path = GUI_DIR / rel
        if path.exists():
            print(f"✓ Found {desc}: {path.name}")
        else:
            print(f"❌ Missing {desc}: {path}")
            missing.append(rel)
    if missing:
        if "frontend/dist/index.html" in missing:
            print(
                "\n→ Build the React app first:\n"
                "    cd scafad/gui/frontend\n"
                "    npm install\n"
                "    npm run build\n"
            )
        sys.exit(1)


def verify_uvicorn_available() -> None:
    """Check uvicorn is importable; if not, print the install hint."""
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print("❌ Missing dependency: uvicorn (FastAPI server runtime)")
        print("\n   Install with:")
        print('   pip install fastapi "uvicorn[standard]" sse-starlette pydantic')
        print()
        sys.exit(1)
    try:
        import fastapi  # noqa: F401
    except ImportError:
        print("❌ Missing dependency: fastapi")
        print("\n   Install with:")
        print('   pip install fastapi "uvicorn[standard]" sse-starlette pydantic')
        print()
        sys.exit(1)
    print("✓ uvicorn + fastapi available")


def port_in_use(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect((host, port))
    except OSError:
        return False
    finally:
        s.close()
    return True


# ──────────────────────────────────────────────────────────────────────
#  Backend
# ──────────────────────────────────────────────────────────────────────

def start_backend():
    """Start the FastAPI backend on BACKEND_PORT in the background."""
    if port_in_use(BACKEND_HOST, BACKEND_PORT):
        print(
            f"⚠️  Port {BACKEND_PORT} is already in use; "
            "assuming a backend is already running and continuing."
        )
        return None

    env = os.environ.copy()
    extra = f"{REPO_ROOT}{os.pathsep}{REPO_ROOT / 'scafad'}"
    env["PYTHONPATH"] = (
        f"{extra}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else extra
    )

    print(f"→ Starting FastAPI backend on http://{BACKEND_HOST}:{BACKEND_PORT}")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "scafad.gui.backend.main:app",
            "--host", BACKEND_HOST,
            "--port", str(BACKEND_PORT),
            "--log-level", "warning",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    deadline = time.time() + BACKEND_BOOT_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            print(f"❌ Backend exited prematurely (code {proc.returncode})")
            print("   Try the dev launcher to see backend logs:")
            print("     scripts\\run_gui_dev.ps1   (Windows)")
            print("     bash scripts/run_gui_dev.sh   (Linux/macOS)")
            sys.exit(1)
        if port_in_use(BACKEND_HOST, BACKEND_PORT):
            print(f"✓ Backend ready on http://{BACKEND_HOST}:{BACKEND_PORT}")
            return proc
        time.sleep(0.3)

    print(f"❌ Backend did not become ready within {BACKEND_BOOT_TIMEOUT}s")
    try:
        proc.terminate()
    except Exception:
        pass
    sys.exit(1)


def stop_process(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────
#  Frontend
# ──────────────────────────────────────────────────────────────────────

def start_frontend(backend_proc):
    """Run the static-file server in the foreground until Ctrl+C."""
    gui_server = GUI_DIR / "gui_server.py"
    print(f"→ Starting GUI server on http://localhost:{FRONTEND_PORT}")
    print()
    print("=" * 64)
    print("🚀 SCAFAD Analyst Console")
    print("=" * 64)
    print(f"   Dashboard : http://localhost:{FRONTEND_PORT}")
    print(f"   Backend   : http://{BACKEND_HOST}:{BACKEND_PORT}  (proxied via /api)")
    print()
    print("   Click  Run Live on AWS  to invoke the deployed Lambda")
    print("   (set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY first — see README §5)")
    print()
    print("   Press Ctrl+C to stop both servers.")
    print("=" * 64)
    print()

    try:
        subprocess.run([sys.executable, str(gui_server)], check=False)
    except KeyboardInterrupt:
        pass
    finally:
        stop_process(backend_proc)
        print("\n✓ Servers stopped.")


# ──────────────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 64)
    print("SCAFAD GUI Initialisation")
    print("=" * 64 + "\n")

    verify_python_version()
    verify_gui_files()
    verify_uvicorn_available()

    print("\n✓ All checks passed. Booting servers...\n")

    backend = start_backend()

    if backend is not None:
        atexit.register(stop_process, backend)

    start_frontend(backend)


if __name__ == "__main__":
    main()
