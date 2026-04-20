"""SleepSense AI unified launcher.

Run API, Celery worker, optional frontend, and optional local infrastructure
(Redis + Mosquitto) from one command so developers do not need multiple terminals.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@dataclass
class ManagedProcess:
    name: str
    command: list[str]
    cwd: Path
    env: dict[str, str]
    process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        print(f"[start] {self.name}: {' '.join(self.command)}")
        self.process = subprocess.Popen(
            self.command,
            cwd=str(self.cwd),
            env=self.env,
            text=True,
        )

    def poll(self) -> int | None:
        return self.process.poll() if self.process else None

    def terminate(self) -> None:
        if not self.process or self.process.poll() is not None:
            return
        print(f"[stop] {self.name}")
        self.process.terminate()

    def kill(self) -> None:
        if not self.process or self.process.poll() is not None:
            return
        print(f"[kill] {self.name}")
        self.process.kill()


class Launcher:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.procs: list[ManagedProcess] = []

    def _python(self) -> str:
        return sys.executable

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        root_str = str(ROOT)
        env["PYTHONPATH"] = f"{root_str}:{env.get('PYTHONPATH', '')}".rstrip(":")
        return env

    def _ensure_binary(self, name: str, help_text: str) -> None:
        if shutil.which(name) is None:
            raise RuntimeError(f"Required executable '{name}' not found. {help_text}")

    def _add(self, name: str, command: list[str], cwd: Path | None = None) -> None:
        self.procs.append(
            ManagedProcess(name=name, command=command, cwd=cwd or ROOT, env=self._env())
        )

    def _port_is_available(self, host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                return False
        return True

    def _ensure_port_available(self, label: str, host: str, port: int, flag: str) -> None:
        if not self._port_is_available(host, port):
            raise RuntimeError(
                f"{label} port {port} is already in use on {host}. "
                f"Stop the existing service or rerun with {flag}."
            )

    def build(self) -> None:
        if self.args.with_redis:
            self._ensure_port_available("Redis", "127.0.0.1", 6379, "--no-redis")

        if self.args.with_mqtt:
            self._ensure_port_available(
                "Mosquitto",
                "127.0.0.1",
                self.args.mqtt_port,
                f"--mqtt-port {self.args.mqtt_port + 1}",
            )

        api_bind_host = self.args.api_host
        if api_bind_host == "0.0.0.0":
            api_bind_host = "127.0.0.1"
        self._ensure_port_available(
            "FastAPI",
            api_bind_host,
            self.args.api_port,
            f"--api-port {self.args.api_port + 1}",
        )

        if self.args.with_redis:
            self._ensure_binary("redis-server", "Install Redis or run with --no-redis.")
            self._add("redis", ["redis-server"])

        if self.args.with_mqtt:
            self._ensure_binary(
                "mosquitto",
                "Install Mosquitto broker or run with --no-mqtt.",
            )
            mqtt_cmd = ["mosquitto", "-p", str(self.args.mqtt_port)]
            self._add("mosquitto", mqtt_cmd)

        self._ensure_binary("celery", "Install API dependencies in your active environment.")
        self._add(
            "celery-worker",
            ["celery", "-A", "tasks", "worker", "--loglevel=info"],
            cwd=ROOT / "api",
        )

        self._ensure_binary("uvicorn", "Install API dependencies in your active environment.")
        self._add(
            "fastapi",
            [
                "uvicorn",
                "main:app",
                "--host",
                self.args.api_host,
                "--port",
                str(self.args.api_port),
                "--reload",
            ],
            cwd=ROOT / "api",
        )

        if self.args.with_frontend:
            npm_bin = "npm.cmd" if os.name == "nt" else "npm"
            self._ensure_binary(
                npm_bin,
                "Install Node.js + npm or launch with --no-frontend.",
            )
            self._add("frontend", [npm_bin, "run", "dev", "--", "--host"], cwd=ROOT / "frontend")

    def start(self) -> int:
        self.build()

        if not self.procs:
            print("No processes selected. Nothing to run.")
            return 0

        def _signal_handler(signum, _frame):
            print(f"\n[signal] Received {signum}, shutting down...")
            self.shutdown()
            raise SystemExit(0)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        for proc in self.procs:
            proc.start()
            time.sleep(0.5)

        self._print_summary()

        try:
            while True:
                for proc in self.procs:
                    code = proc.poll()
                    if code is not None:
                        print(f"[exit] {proc.name} exited with code {code}. Stopping all services.")
                        self.shutdown()
                        return code
                time.sleep(1)
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        for proc in reversed(self.procs):
            proc.terminate()
        time.sleep(1.5)
        for proc in reversed(self.procs):
            proc.kill()

    def _print_summary(self) -> None:
        print("\nSleepSense AI is running:")
        print(f"  • API docs:      http://{self.args.api_host}:{self.args.api_port}/docs")
        if self.args.with_frontend:
            print("  • Frontend:      http://localhost:5173")
        if self.args.with_mqtt:
            print(f"  • MQTT broker:   mqtt://localhost:{self.args.mqtt_port}")
        print("\nPress Ctrl+C to stop all services together.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SleepSense services in a single terminal.")
    parser.add_argument("--api-host", default="0.0.0.0")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--mqtt-port", type=int, default=1883)

    parser.add_argument("--no-frontend", action="store_false", dest="with_frontend")
    parser.add_argument("--no-redis", action="store_false", dest="with_redis")
    parser.add_argument("--no-mqtt", action="store_false", dest="with_mqtt")

    parser.set_defaults(with_frontend=True, with_redis=True, with_mqtt=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    launcher = Launcher(args)
    return launcher.start()


if __name__ == "__main__":
    raise SystemExit(main())
