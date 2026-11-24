#!/usr/bin/env python3
"""Detached supervisor for the private CPU VTuber service and its SSH bridge.

    python3 scripts/puppet_service.py start
    python3 scripts/puppet_service.py status
    python3 scripts/puppet_service.py stop

An existing repository bridge is monitored without taking ownership. A launcher can
be explicitly handed over with --adopt-launcher-pid. PID start times guard against
PID reuse; stop only signals processes this service owns. Credentials are loaded by
run_live.sh, never put into this tool's arguments, state, or log messages.

This supervises processes in the current host/container lifetime. It does not
install an init service or promise recovery after a host/container reboot.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import logging
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Callable
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def process_info(pid: int) -> dict | None:
    """Linux identity, ignoring zombies that cannot supervise or serve anything."""
    if pid <= 1:
        return None
    try:
        data = Path(f"/proc/{pid}/stat").read_text()
        fields = data[data.rfind(")") + 2:].split()
        if fields[0] in ("Z", "X"):
            return None
        return {"pid": pid, "start_ticks": int(fields[19]), "ppid": int(fields[1])}
    except (OSError, ValueError, IndexError):
        return None


def process_ref(pid: int, *, owned: bool, adopted: bool = False) -> dict | None:
    info = process_info(pid)
    if info is None:
        return None
    return {"pid": info["pid"], "start_ticks": info["start_ticks"],
            "owned": owned, "adopted": adopted}


def alive(ref: dict | None) -> bool:
    if not ref or not isinstance(ref.get("pid"), int):
        return False
    info = process_info(ref["pid"])
    return info is not None and info["start_ticks"] == ref.get("start_ticks")


def matches_script(pid: int, script: Path) -> bool:
    """Inspect command paths privately; never return or log another process's argv."""
    try:
        proc = Path(f"/proc/{pid}")
        if proc.stat().st_uid != os.getuid():
            return False
        cwd = (proc / "cwd").resolve()
        arguments = (proc / "cmdline").read_bytes().split(b"\0")
        expected = script.resolve()
        for argument in arguments:
            text = os.fsdecode(argument)
            if Path(text).name != expected.name:
                continue
            candidate = Path(text)
            if not candidate.is_absolute():
                candidate = cwd / candidate
            if candidate.resolve() == expected:
                return True
    except (OSError, ValueError):
        pass
    return False


def find_script(script: Path) -> int | None:
    for proc in sorted(Path("/proc").iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0):
        if proc.name.isdigit():
            pid = int(proc.name)
            if process_info(pid) and matches_script(pid, script):
                return pid
    return None


def descendant_refs(pid: int) -> list[dict]:
    """Snapshot a managed process tree before graceful termination reparents it."""
    known, pending, result = {pid}, [pid], []
    while pending:
        parent = pending.pop()
        try:
            files = list(Path(f"/proc/{parent}/task").glob("*/children"))
            children = set()
            for path in files:
                try:
                    children.update(int(value) for value in path.read_text().split())
                except (OSError, ValueError):
                    pass
            for child in children - known:
                ref = process_ref(child, owned=True)
                if ref is not None:
                    known.add(child)
                    pending.append(child)
                    result.append(ref)
        except OSError:
            pass
    return result


def signal_ref(ref: dict | None, sig: int) -> None:
    if ref and ref.get("owned") and alive(ref):
        try:
            if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
                descriptor = os.pidfd_open(ref["pid"])
                try:
                    if alive(ref):
                        signal.pidfd_send_signal(descriptor, sig)
                finally:
                    os.close(descriptor)
            else:
                os.kill(ref["pid"], sig)
        except ProcessLookupError:
            pass


def terminate_owned(ref: dict | None, timeout: float = 10.0) -> None:
    """Let launcher cleanup run, then stop only its captured, still-identical tree."""
    if not ref or not ref.get("owned") or not alive(ref):
        return
    children = descendant_refs(ref["pid"])
    signal_ref(ref, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and any(alive(r) for r in [ref, *children]):
        time.sleep(0.05)
    remaining = [r for r in [*reversed(children), ref] if alive(r)]
    for child in remaining:
        signal_ref(child, signal.SIGTERM)
    if remaining:
        time.sleep(0.1)
    for child in remaining:
        signal_ref(child, signal.SIGKILL)


def terminate_known(refs: list[dict], timeout: float = 10.0) -> None:
    """Reap previously recorded descendants even after their parent has disappeared."""
    refs = [ref for ref in refs if ref.get("owned") and alive(ref)]
    for ref in refs:
        signal_ref(ref, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while any(alive(ref) for ref in refs) and time.monotonic() < deadline:
        time.sleep(0.05)
    for ref in refs:
        signal_ref(ref, signal.SIGKILL)


def read_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".tmp.{os.getpid()}")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def health(url: str) -> dict:
    """Probe only a loopback endpoint; retain no response body or provider errors."""
    try:
        with urllib.request.urlopen(url, timeout=2.0) as response:
            data = json.loads(response.read(8192))
        if not isinstance(data, dict) or data.get("status") != "ok":
            return {"ok": False, "error": "invalid health response"}
        return {"ok": True, "generator": str(data.get("generator", ""))}
    except Exception as error:
        return {"ok": False, "error": type(error).__name__}


class Supervisor:
    """One stack, injectable commands/probes for offline process-ownership tests."""

    def __init__(self, repo: Path = ROOT, *, state_dir: Path | None = None,
                 log_dir: Path | None = None, frontend_port: int = 8200,
                 backend_port: int = 8201, adopt_launcher_pid: int | None = None,
                 adopt_bridge_pid: int | None = None, bridge_enabled: bool = True,
                 launcher_command: list[str] | None = None,
                 bridge_command: list[str] | None = None,
                 probe: Callable[[str], dict] = health,
                 clock: Callable[[], float] = time.monotonic,
                 health_interval: float = 5.0, unhealthy_seconds: float = 90.0,
                 stop_timeout: float = 10.0):
        self.repo = repo.resolve()
        self.state_dir = state_dir or self.repo / ".cache" / "puppet-service"
        self.log_dir = log_dir or self.repo / ".cache" / "logs"
        self.state_path = self.state_dir / "state.json"
        self.frontend_port, self.backend_port = frontend_port, backend_port
        self.launcher_script = self.repo / "scripts" / "run_live.sh"
        self.bridge_script = self.repo / "scripts" / "bridge_tunnel.sh"
        self.launcher_command = launcher_command or ["bash", str(self.launcher_script), "puppet-full"]
        self.bridge_command = bridge_command or ["bash", str(self.bridge_script)]
        self.check_ports = launcher_command is None
        self.probe, self.clock = probe, clock
        self.health_interval, self.unhealthy_seconds = health_interval, unhealthy_seconds
        self.stop_timeout, self.bridge_enabled = stop_timeout, bridge_enabled
        self.launcher = self.bridge = None
        self.children: dict[str, list[dict]] = {"launcher": [], "bridge": []}
        self.processes: dict[str, subprocess.Popen] = {}
        self.stopping = threading.Event()
        self.next_launch = self.next_bridge = self.next_health = 0.0
        self.started_at = self.clock()
        self.unhealthy_since = None
        self.launch_failures = 0
        self.restart_count = 0
        self.last_health: dict = {}
        self.last_error = ""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(f"puppet-service-{id(self)}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        handler = logging.FileHandler(self.log_dir / "puppet-service.log")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        self.logger.addHandler(handler)

        previous = read_state(self.state_path)
        previous_children = previous.get("children", {})
        for name in self.children:
            self.children[name] = [ref for ref in previous_children.get(name, [])
                                   if isinstance(ref, dict) and ref.get("owned") and alive(ref)]
        for name, script in (("launcher", self.launcher_script), ("bridge", self.bridge_script)):
            ref = previous.get(name)
            if alive(ref) and matches_script(ref["pid"], script):
                setattr(self, name, ref)
        if adopt_launcher_pid is not None:
            if not matches_script(adopt_launcher_pid, self.launcher_script):
                raise ValueError("adopted launcher is not this repository's run_live.sh")
            self.launcher = process_ref(adopt_launcher_pid, owned=True, adopted=True)
            if self.launcher is None:
                raise ValueError("adopted launcher is no longer running")
        if bridge_enabled and (self.bridge is None or adopt_bridge_pid is not None):
            bridge_pid = adopt_bridge_pid if adopt_bridge_pid is not None else find_script(self.bridge_script)
            if bridge_pid is not None:
                if not matches_script(bridge_pid, self.bridge_script):
                    raise ValueError("adopted bridge is not this repository's bridge_tunnel.sh")
                self.bridge = process_ref(bridge_pid, owned=False, adopted=True)
                self.children["bridge"] = []  # borrowing never takes ownership of its SSH children
                if self.bridge is None and adopt_bridge_pid is not None:
                    raise ValueError("adopted bridge is no longer running")
        self._capture_children()

    def _capture_children(self) -> None:
        for name in self.children:
            parent = getattr(self, name)
            if parent and parent.get("owned") and alive(parent):
                refs = [*self.children[name], *descendant_refs(parent["pid"])]
                self.children[name] = list({(ref["pid"], ref["start_ticks"]): ref
                                            for ref in refs if alive(ref)}.values())

    def _spawn(self, name: str, command: list[str]) -> dict:
        environment = os.environ.copy()
        environment.update(HOST="127.0.0.1", PORT=str(self.frontend_port),
                           BACKEND_HOST="127.0.0.1", BACKEND_PORT=str(self.backend_port))
        if name == "bridge":
            environment["LOCAL_PORT"] = str(self.frontend_port)
        output = self.log_dir / f"puppet-service-{name}.log"
        with output.open("ab", buffering=0) as logfile:
            process = subprocess.Popen(command, cwd=self.repo, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=logfile,
                                       stderr=subprocess.STDOUT, close_fds=True,
                                       start_new_session=True)
        self.processes[name] = process
        ref = process_ref(process.pid, owned=True)
        if ref is None:
            process.wait()
            raise RuntimeError(f"{name} exited before startup")
        self.logger.info("started %s pid=%d", name, process.pid)
        return ref

    def _ports_free(self) -> bool:
        if not self.check_ports:
            return True
        for port in (self.frontend_port, self.backend_port):
            try:
                with socket.socket() as listener:
                    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    listener.bind(("127.0.0.1", port))
            except OSError:
                return False
        return True

    def snapshot(self) -> dict:
        return {"schema": 1, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "supervisor": process_ref(os.getpid(), owned=True),
                "launcher": self.launcher, "bridge": self.bridge,
                "children": self.children,
                "bridge_enabled": self.bridge_enabled, "mode": "puppet-full",
                "frontend_port": self.frontend_port, "backend_port": self.backend_port,
                "restart_count": self.restart_count, "health": self.last_health,
                "last_error": self.last_error, "stopping": self.stopping.is_set()}

    def step(self) -> None:
        moment = self.clock()
        self._capture_children()
        for process in self.processes.values():
            process.poll()  # reap exited children before inspecting /proc
        if self.launcher and not alive(self.launcher):
            self.logger.warning("launcher exited; restart pending")
            self.launcher = None
            self.launch_failures += 1
            self.restart_count += 1
            self.next_launch = moment + min(30.0, 2.0 ** min(self.launch_failures - 1, 5))
        if self.launcher is None and self.children["launcher"]:
            terminate_known(self.children["launcher"], self.stop_timeout)
            self.children["launcher"] = []
        if self.launcher is None and moment >= self.next_launch:
            if self._ports_free():
                try:
                    self.launcher = self._spawn("launcher", self.launcher_command)
                    self.started_at = moment
                    self.unhealthy_since = None
                    self.last_error = ""
                except (OSError, RuntimeError) as error:
                    self.last_error = f"launcher start failed: {type(error).__name__}"
                    self.next_launch = moment + 5.0
            else:
                self.last_error = "listener ports occupied; stop or explicitly adopt the existing launcher"
                self.next_launch = moment + 5.0
        if self.bridge_enabled and not alive(self.bridge) and moment >= self.next_bridge:
            terminate_known(self.children["bridge"], self.stop_timeout)
            self.children["bridge"] = []
            # Another controller may have repaired the original bridge in the meantime.
            existing = find_script(self.bridge_script)
            if existing is not None:
                self.bridge = process_ref(existing, owned=False, adopted=True)
            else:
                try:
                    self.bridge = self._spawn("bridge", self.bridge_command)
                except (OSError, RuntimeError):
                    self.bridge = None
                self.next_bridge = moment + 5.0
        if moment >= self.next_health:
            self.last_health = {name: self.probe(f"http://127.0.0.1:{port}/api/health")
                                for name, port in (("frontend", self.frontend_port),
                                                   ("backend", self.backend_port))}
            self.next_health = moment + self.health_interval
            healthy = all(value.get("ok") for value in self.last_health.values())
            if healthy:
                self.unhealthy_since = None
                if moment - self.started_at >= self.health_interval:
                    self.launch_failures = 0
            elif alive(self.launcher):
                if self.unhealthy_since is None:
                    self.unhealthy_since = moment
                if moment - self.unhealthy_since >= self.unhealthy_seconds:
                    self.last_error = "frontend/backend health deadline exceeded; restarting launcher"
                    self.logger.warning(self.last_error)
                    terminate_owned(self.launcher, self.stop_timeout)
        self._capture_children()
        write_state(self.state_path, self.snapshot())

    def close(self) -> None:
        self.stopping.set()
        terminate_owned(self.launcher, self.stop_timeout)
        terminate_known(self.children["launcher"], self.stop_timeout)
        terminate_owned(self.bridge, self.stop_timeout)  # adopted bridges remain untouched
        terminate_known(self.children["bridge"], self.stop_timeout)
        for process in self.processes.values():
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        state = self.snapshot()
        state.update(supervisor=None, launcher=None)
        state["children"] = {"launcher": [], "bridge": []}
        if self.bridge and self.bridge.get("owned"):
            state["bridge"] = None
        write_state(self.state_path, state)
        self.logger.info("supervisor stopped")
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

    def run(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with (self.state_dir / "runtime.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            signal.signal(signal.SIGTERM, lambda *_: self.stopping.set())
            signal.signal(signal.SIGINT, lambda *_: self.stopping.set())
            write_state(self.state_path, self.snapshot())
            try:
                while not self.stopping.is_set():
                    self.step()
                    self.stopping.wait(0.25)
            finally:
                self.close()


def status(state_path: Path, probe: Callable[[str], dict] = health) -> dict:
    state = read_state(state_path)
    result = {"supervisor": {**(state.get("supervisor") or {}), "alive": alive(state.get("supervisor"))},
              "launcher": {**(state.get("launcher") or {}), "alive": alive(state.get("launcher"))},
              "bridge": {**(state.get("bridge") or {}), "alive": alive(state.get("bridge"))},
              "mode": state.get("mode", "puppet-full"), "restart_count": state.get("restart_count", 0),
              "last_error": state.get("last_error", ""), "state_file": str(state_path)}
    result["health"] = {name: probe(f"http://127.0.0.1:{state.get(key, default)}/api/health")
                        for name, key, default in (("frontend", "frontend_port", 8200),
                                                   ("backend", "backend_port", 8201))}
    result["state"] = ("running" if result["supervisor"]["alive"] and result["launcher"]["alive"]
                       and all(value.get("ok") for value in result["health"].values())
                       and (not state.get("bridge_enabled", True) or result["bridge"]["alive"])
                       else "degraded" if result["supervisor"]["alive"] else "stopped")
    return result


def start(args) -> dict:
    args.state_dir.mkdir(parents=True, exist_ok=True)
    path = args.state_dir / "state.json"
    with (args.state_dir / "start.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if alive(read_state(path).get("supervisor")):
            return {"started": False, "already_running": True, "state_file": str(path)}
        for name, script_name in (("adopt_launcher_pid", "run_live.sh"),
                                  ("adopt_bridge_pid", "bridge_tunnel.sh")):
            pid = getattr(args, name)
            if pid is not None and (process_info(pid) is None
                                    or not matches_script(pid, args.repo / "scripts" / script_name)):
                raise ValueError(f"{name.replace('_', ' ')} does not identify this repository's running {script_name}")
        command = [sys.executable, str(Path(__file__).resolve()), "_run",
                   "--repo", str(args.repo),
                   "--state-dir", str(args.state_dir), "--log-dir", str(args.log_dir),
                   "--frontend-port", str(args.frontend_port), "--backend-port", str(args.backend_port),
                   "--health-interval", str(args.health_interval),
                   "--unhealthy-seconds", str(args.unhealthy_seconds), "--stop-timeout", str(args.stop_timeout)]
        for name in ("adopt_launcher_pid", "adopt_bridge_pid"):
            value = getattr(args, name)
            if value is not None:
                command.extend(["--" + name.replace("_", "-"), str(value)])
        if args.no_bridge:
            command.append("--no-bridge")
        daemon = subprocess.Popen(command, cwd=args.repo, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  start_new_session=True, close_fds=True)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            ref = read_state(path).get("supervisor")
            if ref and ref.get("pid") == daemon.pid and alive(ref):
                return {"started": True, "supervisor": ref, "state_file": str(path)}
            if daemon.poll() is not None:
                raise RuntimeError("supervisor could not start; check puppet-service.log and adoption arguments")
            time.sleep(0.05)
        raise RuntimeError("supervisor startup timed out; check puppet-service.log")


def stop(state_path: Path, timeout: float = 10.0) -> dict:
    state = read_state(state_path)
    ref = state.get("supervisor")
    signal_ref(ref, signal.SIGTERM)
    deadline = time.monotonic() + timeout * 2 + 3.0
    while alive(ref) and time.monotonic() < deadline:
        time.sleep(0.05)
    if alive(ref):
        # A deadlocked supervisor still cannot authorize stopping foreign or reused PIDs.
        state = read_state(state_path)
        terminate_owned(state.get("launcher"), 1.0)
        terminate_owned(state.get("bridge"), 1.0)
        for refs in state.get("children", {}).values():
            terminate_known(refs, 1.0)
        signal_ref(ref, signal.SIGKILL)
    elif not state.get("supervisor") or not alive(state.get("supervisor")):
        # Recover owned children left behind if the supervisor was killed previously.
        state = read_state(state_path)
        terminate_owned(state.get("launcher"), timeout)
        terminate_owned(state.get("bridge"), timeout)
        for refs in state.get("children", {}).values():
            terminate_known(refs, timeout)
    return {"stopped": not alive(ref), "state_file": str(state_path)}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["start", "stop", "status", "_run"])
    parser.add_argument("--repo", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--state-dir", type=Path, default=ROOT / ".cache" / "puppet-service")
    parser.add_argument("--log-dir", type=Path, default=ROOT / ".cache" / "logs")
    parser.add_argument("--frontend-port", type=int, default=8200)
    parser.add_argument("--backend-port", type=int, default=8201)
    parser.add_argument("--adopt-launcher-pid", type=int)
    parser.add_argument("--adopt-bridge-pid", type=int)
    parser.add_argument("--no-bridge", action="store_true")
    parser.add_argument("--health-interval", type=float, default=5.0)
    parser.add_argument("--unhealthy-seconds", type=float, default=90.0)
    parser.add_argument("--stop-timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    args.repo, args.state_dir, args.log_dir = args.repo.resolve(), args.state_dir.resolve(), args.log_dir.resolve()
    if not (1 <= args.frontend_port <= 65535 and 1 <= args.backend_port <= 65535
            and args.frontend_port != args.backend_port):
        parser.error("listener ports must be distinct integers from 1 to 65535")
    if min(args.health_interval, args.unhealthy_seconds, args.stop_timeout) <= 0:
        parser.error("health and stop durations must be positive")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "start":
            result = start(args)
        elif args.command == "stop":
            result = stop(args.state_dir / "state.json", args.stop_timeout)
        elif args.command == "status":
            result = status(args.state_dir / "state.json")
        else:
            supervisor = Supervisor(repo=args.repo, state_dir=args.state_dir, log_dir=args.log_dir,
                                    frontend_port=args.frontend_port, backend_port=args.backend_port,
                                    adopt_launcher_pid=args.adopt_launcher_pid,
                                    adopt_bridge_pid=args.adopt_bridge_pid, bridge_enabled=not args.no_bridge,
                                    health_interval=args.health_interval, unhealthy_seconds=args.unhealthy_seconds,
                                    stop_timeout=args.stop_timeout)
            supervisor.run()
            return 0
        print(json.dumps(result, ensure_ascii=False))
        return int(result.get("state") in ("stopped", "degraded")) if args.command == "status" else 0
    except Exception as error:
        # Error text is deliberately limited to internal, credential-free diagnostics.
        print(json.dumps({"error": str(error) if isinstance(error, (ValueError, RuntimeError))
                          else type(error).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
