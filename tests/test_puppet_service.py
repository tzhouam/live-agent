"""Offline supervisor checks: fake launchers/bridges, temporary state, no live services."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from scripts import puppet_service as service


@pytest.fixture
def repo(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("run_live.sh", "bridge_tunnel.sh"):
        (scripts / name).write_text("#!/bin/sh\ntrap 'exit 0' TERM INT\nwhile :; do sleep 0.02; done\n")
    return tmp_path


def spawn(script: Path):
    return subprocess.Popen(["bash", str(script)], cwd=script.parents[1],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def finish(process):
    if process.poll() is None:
        service.terminate_owned(service.process_ref(process.pid, owned=True), timeout=0.2)
    process.wait(timeout=2)


def controller(repo, **kwargs):
    return service.Supervisor(repo=repo, launcher_command=["bash", str(repo / "scripts/run_live.sh"), "puppet-full"],
                              bridge_command=["bash", str(repo / "scripts/bridge_tunnel.sh")],
                              bridge_enabled=kwargs.pop("bridge_enabled", False),
                              probe=kwargs.pop("probe", lambda _: {"ok": True, "generator": "puppet"}),
                              stop_timeout=0.2, **kwargs)


def test_launcher_failure_restarts_with_backoff_and_persists_identity(repo):
    clock = [0.0]
    supervisor = controller(repo, clock=lambda: clock[0])
    try:
        supervisor.step()
        original = supervisor.launcher.copy()
        os.kill(original["pid"], signal.SIGKILL)
        supervisor.processes["launcher"].wait(timeout=2)
        clock[0] = 1.0
        supervisor.step()
        assert supervisor.launcher is None and supervisor.restart_count == 1
        clock[0] = 3.0
        supervisor.step()
        assert service.alive(supervisor.launcher)
        assert supervisor.launcher["pid"] != original["pid"]
        state = service.read_state(supervisor.state_path)
        assert state["launcher"]["start_ticks"] == supervisor.launcher["start_ticks"]
        assert state["restart_count"] == 1
    finally:
        supervisor.close()


def test_existing_bridge_is_adopted_and_survives_service_stop(repo):
    bridge = spawn(repo / "scripts/bridge_tunnel.sh")
    supervisor = controller(repo, bridge_enabled=True)
    try:
        supervisor.step()
        assert supervisor.bridge["pid"] == bridge.pid
        assert supervisor.bridge["owned"] is False
        assert "bridge" not in supervisor.processes
        supervisor.close()
        assert bridge.poll() is None
        assert service.alive(service.read_state(supervisor.state_path)["bridge"])
    finally:
        finish(bridge)


def test_explicit_launcher_handoff_stops_only_adopted_tree(repo):
    launcher = spawn(repo / "scripts/run_live.sh")
    foreign = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    supervisor = controller(repo, adopt_launcher_pid=launcher.pid)
    try:
        supervisor.step()
        assert supervisor.launcher["pid"] == launcher.pid
        assert supervisor.launcher["adopted"] and supervisor.launcher["owned"]
        assert "launcher" not in supervisor.processes
        supervisor.close()
        launcher.wait(timeout=2)
        assert foreign.poll() is None
    finally:
        finish(launcher)
        finish(foreign)


def test_stale_pid_identity_and_unowned_process_are_never_signalled(repo):
    process = spawn(repo / "scripts/run_live.sh")
    try:
        ref = service.process_ref(process.pid, owned=True)
        stale = {**ref, "start_ticks": ref["start_ticks"] + 1}
        assert not service.alive(stale)
        service.terminate_owned(stale, timeout=0.01)
        service.terminate_owned({**ref, "owned": False}, timeout=0.01)
        assert process.poll() is None
    finally:
        finish(process)


def test_persistent_failed_health_restarts_launcher(repo):
    clock = [0.0]
    supervisor = controller(repo, clock=lambda: clock[0], health_interval=1,
                            unhealthy_seconds=3, probe=lambda _: {"ok": False, "error": "unavailable"})
    try:
        supervisor.step()
        original = supervisor.launcher.copy()
        clock[0] = 2.0
        supervisor.step()
        assert service.alive(original)
        clock[0] = 3.0
        supervisor.step()
        assert not service.alive(original)
        clock[0] = 4.0
        supervisor.step()
        clock[0] = 6.0
        supervisor.step()
        assert service.alive(supervisor.launcher)
        assert supervisor.launcher["pid"] != original["pid"]
    finally:
        supervisor.close()


def test_abrupt_launcher_exit_cleans_recorded_orphans_before_restart(repo):
    script = repo / "scripts/run_live.sh"
    script.write_text("#!/bin/sh\nsleep 60 &\nwait\n")
    clock = [0.0]
    supervisor = controller(repo, clock=lambda: clock[0])
    try:
        supervisor.step()
        deadline = time.monotonic() + 2
        while not supervisor.children["launcher"] and time.monotonic() < deadline:
            time.sleep(0.02)
            supervisor.step()
        children = supervisor.children["launcher"][:]
        assert children and any(service.alive(ref) for ref in children)
        os.kill(supervisor.launcher["pid"], signal.SIGKILL)
        supervisor.processes["launcher"].wait(timeout=2)
        assert any(service.alive(ref) for ref in children)
        clock[0] = 1.0
        supervisor.step()
        assert all(not service.alive(ref) for ref in children)
        clock[0] = 3.0
        supervisor.step()
        assert service.alive(supervisor.launcher)
    finally:
        supervisor.close()


def test_occupied_ports_do_not_kill_or_adopt_foreign_listeners(repo, monkeypatch):
    supervisor = controller(repo)
    monkeypatch.setattr(supervisor, "_ports_free", lambda: False)
    try:
        supervisor.step()
        assert supervisor.launcher is None and not supervisor.processes
        assert "listener ports occupied" in service.read_state(supervisor.state_path)["last_error"]
    finally:
        supervisor.close()


def test_state_status_and_logs_do_not_contain_api_credentials(repo, monkeypatch):
    private_value = "test-provider-key-must-not-be-recorded"
    monkeypatch.setenv("LLM_API_KEY", private_value)
    supervisor = controller(repo)
    try:
        supervisor.step()
        status = service.status(supervisor.state_path, lambda _: {"ok": True})
        assert status["state"] == "running"
        assert status["launcher"]["alive"]
        assert private_value not in json.dumps(status)
        assert private_value not in supervisor.state_path.read_text()
        assert private_value not in (supervisor.log_dir / "puppet-service.log").read_text()
        assert supervisor.state_path.stat().st_mode & 0o777 == 0o600
    finally:
        supervisor.close()


def test_adoption_rejects_unrelated_process(repo):
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with pytest.raises(ValueError, match="not this repository"):
            controller(repo, adopt_launcher_pid=process.pid)
        assert process.poll() is None
    finally:
        finish(process)


def test_detached_cli_start_is_idempotent_and_stop_preserves_external_bridge(repo):
    bridge = spawn(repo / "scripts/bridge_tunnel.sh")
    state_dir, log_dir = repo / "state", repo / "logs"
    # Fake scripts never bind any ports; unavailable probes are allowed during startup.
    common = ["--repo", str(repo), "--state-dir", str(state_dir), "--log-dir", str(log_dir),
              "--frontend-port", "62451", "--backend-port", "62452", "--stop-timeout", "0.2"]
    script = str(Path(service.__file__).resolve())
    def cli(action):
        return subprocess.run([sys.executable, script, action, *common], capture_output=True,
                              text=True, timeout=10, check=True)
    try:
        first = json.loads(cli("start").stdout)
        assert first["started"]
        second = json.loads(cli("start").stdout)
        assert second["already_running"] and not second["started"]
        deadline = time.monotonic() + 3
        while not service.read_state(state_dir / "state.json").get("launcher") and time.monotonic() < deadline:
            time.sleep(0.05)
        state = service.read_state(state_dir / "state.json")
        assert service.alive(state["launcher"])
        assert state["bridge"]["pid"] == bridge.pid and not state["bridge"]["owned"]
        assert json.loads(cli("stop").stdout)["stopped"]
        assert not service.alive(first["supervisor"])
        assert bridge.poll() is None
    finally:
        service.stop(state_dir / "state.json", timeout=0.2)
        finish(bridge)
