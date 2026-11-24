"""Launcher preflight checks with executable stubs; no GPU or model process starts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required by the launcher")


@pytest.fixture
def launcher_env(tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    calls = tmp_path / "gpu_calls.jsonl"
    gpu = tools / "gpu"
    gpu.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['FAKE_GPU_CALLS'], 'a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1] == 'run': sys.exit(9)\n"
        "if sys.argv[1] == 'status':\n"
        "    print(' GPU │ NOTE ')\n"
        "    sys.exit(0)\n"
        "sys.exit(2)\n"
    )
    gpu.chmod(0o755)
    omni = tmp_path / "omni"
    executable = omni / ".venv" / "bin" / "vllm"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 99\n")
    executable.chmod(0o755)
    # Reserve all candidates together so even the fixture cannot select duplicates.
    sockets = [socket.socket() for _ in range(3)]
    try:
        for sock in sockets:
            sock.bind(("127.0.0.1", 0))
        ports = [str(sock.getsockname()[1]) for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()
    env = dict(
        os.environ,
        PATH=str(tools) + os.pathsep + os.environ["PATH"],
        FAKE_GPU_CALLS=str(calls),
        OMNI_DIR=str(omni),
        PORT=ports[0],
        BACKEND_PORT=ports[1],
        OMNI_PORT=ports[2],
        HOST="127.0.0.1",
        BACKEND_HOST="127.0.0.1",
        PERSONA="hanfu",
        HELPERS="1",
        IMAGES="0",
        SKIP_LLM="0",
        LLM_URL="http://127.0.0.1:8101/v1",
        LLM_API_KEY="",
        LLM_API_KEY_FILE=str(tmp_path / "nonexistent_key"),
        RECORD="0",
        READY_TIMEOUT="2",
        STUDENT_STORE="",
        MEMORY_DB="",
        SESSION_LOG_DIR="",
    )
    return env, calls


@pytest.mark.parametrize(
    "mode, overrides, expected",
    [
        ("omni", {"OMNI_PORT": "8102"}, "duplicate planned listener port: 8102"),
        ("omni", {"OMNI_PORT": "8103"}, "duplicate planned listener port: 8103"),
        ("omni", {"OMNI_PORT": "8104", "IMAGES": "1"}, "duplicate planned listener port: 8104"),
        ("omni", {"PORT": "8200", "OMNI_PORT": "08200"}, "duplicate planned listener port: 8200"),
        ("omni", {"BACKEND_PORT": "8201", "OMNI_PORT": "08201"}, "duplicate planned listener port: 8201"),
        ("omni", {"OMNI_PORT": "0"}, "invalid port: 0"),
        ("omni", {"OMNI_PORT": "65536"}, "invalid port: 65536"),
        ("omni", {"OMNI_PORT": "not-a-port"}, "invalid port: not-a-port"),
        ("omni", {"OMNI_PORT": "18446744073709560616"}, "invalid port: 18446744073709560616"),
        ("full", {"BACKEND_PORT": "8102"}, "duplicate planned listener port: 8102"),
        ("packed", {"PORT": "8103"}, "duplicate planned listener port: 8103"),
    ],
)
def test_invalid_planned_ports_fail_before_start(launcher_env, mode, overrides, expected):
    env, calls = launcher_env
    result = subprocess.run(
        [str(ROOT / "scripts/run_live.sh"), mode],
        env={**env, **overrides}, cwd=ROOT, text=True, capture_output=True, timeout=15,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert expected in result.stdout
    assert "[run_live] frontend log:" not in result.stdout
    assert not calls.exists(), "preflight must not invoke even the fake GPU command"


def test_unique_ports_reach_fake_gpu_boundary_and_clean_frontend(launcher_env):
    env, calls = launcher_env
    expected_omni_port = env["OMNI_PORT"]
    env = {**env, "HELPERS": "0", "OMNI_PORT": "0" + expected_omni_port}
    result = subprocess.run(
        [str(ROOT / "scripts/run_live.sh"), "omni"],
        env=env, cwd=ROOT, text=True, capture_output=True, timeout=20,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    runs = [command for command in commands if command[0] == "run"]
    assert len(runs) == 1
    run = runs[0]
    assert ".venv/bin/vllm" in run
    assert run[run.index("--port") + 1] == expected_omni_port
    assert "duplicate planned listener port" not in result.stdout
    assert "[run_live] ready:" not in result.stdout
    for name in ("PORT", "BACKEND_PORT"):
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", int(env[name]))) != 0


@pytest.mark.parametrize("persona, expected", [(None, "teacher"), ("hanfu", "hanfu")])
def test_launcher_default_teacher_and_explicit_persona(launcher_env, tmp_path, persona, expected):
    env, gpu_calls = launcher_env
    env = dict(env)
    env.pop("PERSONA")
    if persona is not None:
        env["PERSONA"] = persona
    backend_calls = tmp_path / "backend_args.json"
    env["FAKE_BACKEND_CALLS"] = str(backend_calls)
    python = Path(env["PATH"].split(os.pathsep)[0]) / "python3"
    python.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "if sys.argv[1:3] == ['-m', 'live_agent.backend.app']:\n"
        "    with open(os.environ['FAKE_BACKEND_CALLS'], 'w') as output:\n"
        "        json.dump(sys.argv[3:], output)\n"
        "    sys.exit(17)\n"
        "os.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n"
    )
    python.chmod(0o755)
    result = subprocess.run(
        [str(ROOT / "scripts/run_live.sh"), "demo"], env=env, cwd=ROOT,
        text=True, capture_output=True, timeout=15,
    )
    assert result.returncode != 0
    args = json.loads(backend_calls.read_text())
    assert args[args.index("--config") + 1] == f"configs/persona_{expected}"
    assert not gpu_calls.exists()


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"PUPPET_TTS": "synth"}, ["--puppet-tts", "synth"]),
        ({"TTS_URL": "http://tts.example/v1", "TTS_MODEL": "voice-a", "TTS_VOICE": "bo"},
         ["--puppet-tts", "url", "--tts-url", "http://tts.example/v1", "--tts-model", "voice-a",
          "--puppet-tts-voice", "bo"]),
    ],
)
def test_launcher_puppet_mode_is_cpu_only(launcher_env, tmp_path, overrides, expected):
    env, gpu_calls = launcher_env
    env = dict(env, **overrides)
    backend_calls = tmp_path / "backend_args.json"
    env["FAKE_BACKEND_CALLS"] = str(backend_calls)
    python = Path(env["PATH"].split(os.pathsep)[0]) / "python3"
    python.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "if sys.argv[1:3] == ['-m', 'live_agent.backend.app']:\n"
        "    with open(os.environ['FAKE_BACKEND_CALLS'], 'w') as output:\n"
        "        json.dump(sys.argv[3:], output)\n"
        "    sys.exit(17)\n"
        "os.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n"
    )
    python.chmod(0o755)
    result = subprocess.run(
        [str(ROOT / "scripts/run_live.sh"), "puppet"], env=env, cwd=ROOT,
        text=True, capture_output=True, timeout=15,
    )
    assert result.returncode != 0
    args = json.loads(backend_calls.read_text())
    assert args[args.index("--generator") + 1] == "puppet"
    for flag, value in zip(expected[::2], expected[1::2]):
        assert args[args.index(flag) + 1] == value
    assert "--llm-url" in args and args[args.index("--llm-url") + 1] == "scripted"  # CPU-only responder
    assert args[args.index("--student") + 1] == "demo"
    assert args[args.index("--students") + 1] == "demo"
    assert not gpu_calls.exists(), "puppet mode must not reserve GPUs"


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({}, {
            "--llm-url": "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic",
            "--llm-model": "qwen3.8-flash",
            "--vlm-url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
            "--vlm-model": "qwen3.8-flash",
            "--asr-url": "wss://token-plan.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime",
            "--asr-model": "qwen-audio-3.0-realtime-plus",
        }),
        ({"LLM_URL": "http://127.0.0.1:8101/v1", "LLM_MODEL": "custom-chat",
          "HOSTED_VLM_URL": "https://vision.example/v1", "HOSTED_VLM_MODEL": "custom-vision",
          "HOSTED_ASR_URL": "https://speech.example/v1", "HOSTED_ASR_MODEL": "custom-speech",
          "STUDENT": "private_learner", "STUDENTS": "private_learner,demo",
          "STUDENT_STORE": "/tmp/mesh service/students",
          "MEMORY_DB": "/tmp/mesh service/memory.sqlite",
          "SESSION_LOG_DIR": "/tmp/mesh service/sessions"}, {
            "--llm-url": "http://127.0.0.1:8101/v1", "--llm-model": "custom-chat",
            "--vlm-url": "https://vision.example/v1", "--vlm-model": "custom-vision",
            "--asr-url": "https://speech.example/v1", "--asr-model": "custom-speech",
        }),
    ],
)
def test_puppet_full_uses_real_providers_without_gpu_processes(launcher_env, tmp_path, overrides, expected):
    env, gpu_calls = launcher_env
    env = dict(env)
    env.pop("LLM_URL")
    env.pop("LLM_MODEL", None)
    # A private key file reaches only the backend environment, never command-line arguments or logs.
    key_file = tmp_path / "key"
    key_file.write_text("fake-launcher-test-key\n")
    key_file.chmod(0o600)
    env.update(PERSONA="teacher", LLM_API_KEY_FILE=str(key_file), FAKE_BACKEND_CALLS=str(tmp_path / "backend.json"),
               IMAGES="1", HELPERS="1", PUPPET_TTS="edge", **overrides)
    python = Path(env["PATH"].split(os.pathsep)[0]) / "python3"
    python.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "if sys.argv[1:3] == ['-m', 'live_agent.backend.app']:\n"
        "    with open(os.environ['FAKE_BACKEND_CALLS'], 'w') as output:\n"
        "        json.dump({'args': sys.argv[3:], 'key': os.environ.get('LLM_API_KEY')}, output)\n"
        "    sys.exit(17)\n"
        "os.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n"
    )
    python.chmod(0o755)
    result = subprocess.run(
        [str(ROOT / "scripts/run_live.sh"), "puppet-full"], env=env, cwd=ROOT,
        text=True, capture_output=True, timeout=15,
    )
    assert result.returncode != 0  # The fake backend exits deliberately.
    call = json.loads(Path(env["FAKE_BACKEND_CALLS"]).read_text())
    args = call["args"]
    assert args[args.index("--generator") + 1] == "puppet"
    assert args[args.index("--puppet-tts") + 1] == "edge"
    assert args[args.index("--student") + 1] == overrides.get("STUDENT", "learner")
    assert args[args.index("--students") + 1] == overrides.get("STUDENTS", "learner,demo")
    assert "--answer-self-check" in args
    assert args[args.index("--lesson-self-check") + 1] == "revise"
    for option, variable in (("--student-store", "STUDENT_STORE"), ("--memory-db", "MEMORY_DB"),
                             ("--log-dir", "SESSION_LOG_DIR")):
        if variable in overrides:
            assert args.count(option) == 1
            assert args[args.index(option) + 1] == overrides[variable]
        else:
            assert option not in args, "Unset storage paths must retain backend defaults"
    for flag, value in expected.items():
        assert args.count(flag) == 1
        assert args[args.index(flag) + 1] == value
    assert "--image-url" not in args, "CPU mode must not point at an unstarted image model"
    assert call["key"] == "fake-launcher-test-key"
    assert call["key"] not in result.stdout + result.stderr
    assert call["key"] not in args
    assert not gpu_calls.exists(), "full puppet mode must not start or release GPU reservations"
    for name in ("PORT", "BACKEND_PORT"):
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", int(env[name]))) != 0


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"LLM_API_KEY": ""}, "puppet-full needs LLM_API_KEY"),
        ({"LLM_URL": "scripted"}, "puppet-full needs an HTTP(S) LLM_URL"),
        ({"HOSTED_VLM_URL": "mock"}, "puppet-full needs an HTTP(S) HOSTED_VLM_URL"),
        ({"HOSTED_ASR_URL": "mock"}, "puppet-full needs an HTTP(S) or WebSocket HOSTED_ASR_URL"),
        ({"PUPPET_TTS": "piper", "PUPPET_MODEL": ""}, "puppet + piper needs PUPPET_MODEL"),
        ({"PUPPET_TTS": "unknown"}, "PUPPET_TTS must be edge, synth or piper"),
    ],
)
def test_puppet_full_bad_configuration_fails_before_start(launcher_env, overrides, expected):
    env, gpu_calls = launcher_env
    result = subprocess.run(
        [str(ROOT / "scripts/run_live.sh"), "puppet-full"],
        env={**env, "LLM_API_KEY": "fake-preflight-key", "PUPPET_TTS": "edge", **overrides},
        cwd=ROOT, text=True, capture_output=True, timeout=15,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert expected in result.stdout
    assert "[run_live] frontend log:" not in result.stdout
    assert "fake-preflight-key" not in result.stdout + result.stderr
    assert not gpu_calls.exists()
