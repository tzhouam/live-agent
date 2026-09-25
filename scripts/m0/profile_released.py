"""M0 component profiling of the *released* TaoMate-H3 T2AV path (commit 6b2f998).

Runs the same two torchrun stages as ``python -m taomate_h3`` (cli.py:219-229):
(1) base-H3 audio teacher for all prompts, (2) streaming student + one-shot publication,
but through ``profile_entry.py`` so per-component timestamps are logged. It also samples
``nvidia-smi`` memory for the reserved GPUs and keeps the teacher milestones and the
per-request latents for later parity checks against our streaming worker.

Must run inside a canhazgpu reservation, e.g.::

    gpu run --gpu-ids 0,1,2,3 --timeout 1h --note "live-agent M0: released baseline" -- \
      .venvs/taomate-h3/bin/python scripts/m0/profile_released.py --tag r4_480p_rep1

Devices are taken from ``CUDA_VISIBLE_DEVICES`` (set by ``gpu run``); the CLI's own
default of ``0..gpus-1`` would ignore the reservation, so we pass them explicitly.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CLONE = REPO / "external" / "TaoMate-H3"
DEFAULT_MODEL_ROOT = Path(
    "/data/models/hub/models--MiniMaxAI--MiniMax-H3/snapshots/42ed227ee7df40d41602854ae760620d6eb651fe"
)
DEFAULT_ADAPTER = REPO / ".cache" / "models" / "TaoMate-H3"


def _git_head(path: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--prompt-json", type=Path, default=CLONE / "examples" / "prompts_10s.json")
    parser.add_argument("--resolution", default="480x864")
    parser.add_argument("--seed", type=int, default=8301)
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--adapter", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--out-root", type=Path, default=REPO / ".cache" / "m0" / "runs")
    args = parser.parse_args()

    # The default /usr/local/bin/ffmpeg on this host lacks libx264; /usr/bin/ffmpeg has it.
    os.environ["PATH"] = str(REPO / ".venvs" / "taomate-h3" / "ffbin") + os.pathsep + os.environ["PATH"]
    from taomate_h3 import cli, teacher
    from taomate_h3.config import build_run_config, write_run_config

    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    if not visible:
        raise SystemExit("CUDA_VISIBLE_DEVICES is unset: run inside `gpu run`")
    devices = visible
    gpu_count = len(devices.split(","))
    out = args.out_root / f"{args.tag}-{time.strftime('%Y%m%dT%H%M%S')}"
    out.mkdir(parents=True)
    events = out / "events.jsonl"

    config = build_run_config(
        model_root=args.model_root,
        adapter=args.adapter,
        output_dir=out / "output",
        prompt=None,
        prompt_json=args.prompt_json,
        duration_seconds=None,
        resolution=args.resolution,
        seed=args.seed,
        gpu_count=gpu_count,
        devices=devices,
    )
    cli._validate_media_tools()
    cli._validate_acceleration_runtime()
    cli._validate_input_paths(config)

    meta = {
        "tag": args.tag,
        "date": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "live_agent_head": _git_head(REPO),
        "taomate_h3_head": _git_head(CLONE),
        "model_root": str(args.model_root),
        "adapter": str(args.adapter),
        "devices": devices,
        "gpu_count": gpu_count,
        "resolution": args.resolution,
        "prompt_json": str(args.prompt_json),
        "request_count": config.request_count,
        "python": sys.version,
    }
    try:
        import torch
        import vllm

        meta["torch"] = torch.__version__
        meta["vllm"] = vllm.__version__
    except Exception:
        pass

    environment = os.environ.copy()
    environment.update(
        {
            "CUDA_VISIBLE_DEVICES": devices,
            "OMP_NUM_THREADS": "1",
            "M0_EVENT_LOG": str(events),
            "M0_LATENT_DIR": str(out / "latents"),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    entry = str(Path(__file__).with_name("profile_entry.py"))
    sampler = subprocess.Popen(
        [
            "nvidia-smi",
            "--query-gpu=timestamp,index,memory.used,utilization.gpu",
            "--format=csv,noheader,nounits",
            "-lms",
            "500",
            "-i",
            devices,
        ],
        stdout=open(out / "nvidia_smi.csv", "w"),
        stderr=subprocess.DEVNULL,
    )
    stages: dict[str, dict[str, float]] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="la-m0-guidance-", dir="/dev/shm") as tmp:
            guidance = Path(tmp) / "guidance"
            guidance.mkdir()
            tconfig = teacher.TeacherConfig(
                model_root=config.model_root,
                output_dir=guidance,
                prompts=config.prompts,
                request_seeds=config.request_seeds,
                duration_seconds=config.duration_seconds,
                width=config.width,
                height=config.height,
                resolution=config.resolution,
                devices=config.devices,
                audio_seed_base=config.seed,
                gpu_count=config.gpu_count,
                ulysses_degree=config.ulysses_degree,
            )
            prompt_path = Path(tmp) / "prompts.json"
            teacher_cmd = [
                sys.executable, "-m", "torch.distributed.run", "--standalone",
                f"--nproc-per-node={gpu_count}", entry, "teacher",
                *teacher._worker_arguments(tconfig, prompt_path=prompt_path),
            ]
            t0 = time.time()
            with open(out / "teacher.log", "w") as log:
                subprocess.run(teacher_cmd, check=True, env=environment, stdout=log,
                               stderr=subprocess.STDOUT)
            stages["teacher_process"] = {"start": t0, "end": time.time()}
            shutil.copytree(guidance, out / "guidance")

            (out / "output").mkdir()
            config_path = out / "output" / "run_config.json"
            write_run_config(config_path, config)
            worker_cmd = [
                sys.executable, "-m", "torch.distributed.run", "--standalone",
                f"--nproc-per-node={gpu_count}", entry, "worker",
                "--config", str(config_path), "--audio-guidance-dir", str(guidance),
            ]
            t0 = time.time()
            with open(out / "worker.log", "w") as log:
                subprocess.run(worker_cmd, check=True, env=environment, stdout=log,
                               stderr=subprocess.STDOUT)
            stages["worker_process"] = {"start": t0, "end": time.time()}
    finally:
        sampler.terminate()
        meta["stages"] = stages
        (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
