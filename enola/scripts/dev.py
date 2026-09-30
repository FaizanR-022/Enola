"""Start everything Enola needs in one terminal.

    python -m enola.scripts.dev

Brings up the database, applies migrations, then runs the API, the worker and the web
dev server side by side with prefixed output. Ctrl+C stops all of them cleanly.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from enola.core.config import get_settings
from enola.core.db import get_engine

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

RESET = "\033[0m"
COLOURS = {"api": "\033[36m", "worker": "\033[35m", "web": "\033[32m", "enola": "\033[33m"}
USE_COLOUR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def tint(name: str, text_: str) -> str:
    if not USE_COLOUR:
        return text_
    return f"{COLOURS.get(name, '')}{text_}{RESET}"


def say(message: str) -> None:
    print(f"{tint('enola', '[enola ]')} {message}", flush=True)


@dataclass
class Service:
    name: str
    argv: list[str]
    cwd: Path
    proc: subprocess.Popen[str] | None = None


def pump(service: Service) -> None:
    """Echo a child's output with its name in front, so one terminal stays readable."""
    assert service.proc is not None and service.proc.stdout is not None
    label = tint(service.name, f"[{service.name:<6}]")
    for line in service.proc.stdout:
        print(f"{label} {line.rstrip()}", flush=True)


def run(argv: list[str], cwd: Path | None = None) -> int:
    return subprocess.call(argv, cwd=cwd or ROOT)


def kill_tree(proc: subprocess.Popen[str]) -> None:
    """Kill a child and everything it spawned.

    uvicorn --reload is a supervisor: terminating it leaves the worker holding the
    port, so the next run fails with "address in use". npm does the same with vite."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()


def compose_up() -> None:
    if shutil.which("docker") is None:
        say("docker not found on PATH. Start Docker Desktop, or run Postgres yourself.")
        raise SystemExit(1)
    say("starting postgres...")
    if run(["docker", "compose", "up", "-d"]) != 0:
        say("docker compose failed. Is Docker Desktop running?")
        raise SystemExit(1)


def wait_for_db(timeout: float = 60.0) -> None:
    """Compose reports the container up before Postgres accepts connections."""
    settings = get_settings()
    engine = get_engine(settings.database_url)
    deadline = time.monotonic() + timeout
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            say("postgres ready")
            return
        except Exception:
            if time.monotonic() > deadline:
                say(f"postgres did not accept connections within {timeout:.0f}s")
                raise SystemExit(1) from None
            time.sleep(1.0)


def migrate() -> None:
    say("applying migrations...")
    if run([sys.executable, "-m", "alembic", "upgrade", "head"]) != 0:
        say("alembic upgrade failed")
        raise SystemExit(1)


def build_services(args: argparse.Namespace) -> list[Service]:
    settings = get_settings()
    services: list[Service] = [
        Service(
            "api",
            [sys.executable, "-m", "uvicorn", "enola.api.main:app",
             "--host", settings.api_host, "--port", str(settings.api_port)]
            + ([] if args.no_reload else ["--reload"]),
            ROOT,
        )
    ]
    if not args.no_worker:
        services.append(Service("worker", [sys.executable, "-m", "enola.workers.scheduler"], ROOT))
    if not args.no_web:
        npm = shutil.which("npm") or "npm"
        services.append(Service("web", [npm, "run", "dev"], WEB))
    return services


def start(services: list[Service]) -> None:
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "FORCE_COLOR": "1"}
    for service in services:
        service.proc = subprocess.Popen(
            service.argv,
            cwd=service.cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            # Windows: npm/vite are .cmd shims, which need the shell resolution
            # CreateProcess gives them via shutil.which above; no shell=True here,
            # so a crashing child can't leave an orphaned shell behind.
        )
        threading.Thread(target=pump, args=(service,), daemon=True).start()
        say(f"{service.name} started (pid {service.proc.pid})")


def stop(services: list[Service]) -> None:
    say("shutting down...")
    for service in reversed(services):
        if service.proc and service.proc.poll() is None:
            service.proc.terminate()
    deadline = time.monotonic() + 8
    for service in reversed(services):
        if not service.proc:
            continue
        remaining = max(0.5, deadline - time.monotonic())
        try:
            service.proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            say(f"{service.name} ignored terminate; killing its tree")
        # Always sweep the tree: a supervisor that exits cleanly can still leave a
        # worker behind, and a leaked worker means the next run cannot bind the port.
        kill_tree(service.proc)
    say("stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all of Enola in one terminal.")
    parser.add_argument("--no-web", action="store_true", help="skip the Vite dev server")
    parser.add_argument("--no-worker", action="store_true", help="skip the scheduler")
    parser.add_argument("--no-reload", action="store_true", help="run the API without --reload")
    parser.add_argument("--no-open", action="store_true", help="do not open the browser")
    parser.add_argument("--no-db", action="store_true", help="assume Postgres is already running")
    args = parser.parse_args()

    if not args.no_db:
        compose_up()
        wait_for_db()
        migrate()

    services = build_services(args)
    start(services)

    web_url = "http://localhost:5173"
    if not args.no_open and not args.no_web:
        threading.Timer(3.0, lambda: webbrowser.open(web_url)).start()
    say(f"Enola is up at {web_url}   (Ctrl+C to stop everything)")

    # Signal handling: the default SIGINT handler raises KeyboardInterrupt here while
    # children get the console's Ctrl+C too, so terminate() is belt and braces.
    try:
        while True:
            for service in services:
                if service.proc and service.proc.poll() is not None:
                    say(f"{service.name} exited with code {service.proc.returncode}")
                    raise SystemExit(service.proc.returncode or 1)
            time.sleep(0.5)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        stop(services)


if __name__ == "__main__":
    main()
