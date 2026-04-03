"""
Run Script — Start Backend + Frontend
=======================================
Starts both the FastAPI backend and Vite frontend dev server.

Usage: python scripts/run.py
"""

import os
import sys
import subprocess
import signal
import time
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

processes = []


def start_backend():
    """Start the FastAPI backend server."""
    print("[Backend] Starting on http://127.0.0.1:8000 ...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app",
         "--host", "127.0.0.1", "--port", "8000", "--reload"],
        cwd=PROJECT_ROOT,
    )
    processes.append(proc)
    return proc


def start_frontend():
    """Start the Vite frontend dev server."""
    frontend_dir = os.path.join(PROJECT_ROOT, "frontend")
    print("[Frontend] Starting on http://localhost:5173 ...")
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True,
    )
    processes.append(proc)
    return proc


def cleanup(signum=None, frame=None):
    """Terminate all child processes."""
    print("\n\n[Shutdown] Stopping all services...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            p.kill()
    print("[Shutdown] Done.")
    sys.exit(0)


def main():
    print("=" * 60)
    print("🚀 VoicePay — Starting Application")
    print("=" * 60)

    # Register cleanup handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Start services
    backend = start_backend()
    time.sleep(2)  # Give backend a moment to start
    frontend = start_frontend()

    print("\n" + "=" * 60)
    print("✅ Application Running!")
    print("=" * 60)
    print(f"\n  🌐 Frontend:  http://localhost:5173")
    print(f"  📡 Backend:   http://127.0.0.1:8000")
    print(f"  📚 API Docs:  http://127.0.0.1:8000/docs")
    print(f"\n  Press Ctrl+C to stop all services.")
    print("=" * 60 + "\n")

    # Wait for either process to exit
    try:
        while True:
            if backend.poll() is not None:
                print("[Backend] Process exited!")
                cleanup()
            if frontend.poll() is not None:
                print("[Frontend] Process exited!")
                cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
