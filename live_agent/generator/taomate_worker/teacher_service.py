"""Resident base-H3 audio teacher + text encoder (torchrun entry, role ``teacher``).

Reuses ``taomate_h3.teacher._generate_request`` from the read-only clone unchanged, but
instead of iterating over a precompiled prompt list (teacher.py:429-473) it serves one
``teach`` command per locked prompt and keeps the previous request's clean audio tail
(``tail40_rollover``) as session state. The Qwen3-VL text encoder stays on the GPU; the
encoded prompt is shipped to the student inside the ``teacher_done`` blob so the student
does not need its own resident text encoder.

Launch (normally done by ``TaoMateH3Generator``)::

    torchrun --standalone --nproc-per-node=N -m live_agent.generator.taomate_worker.teacher_service \
        --model-root <H3 root> --width 864 --height 480
"""

from __future__ import annotations

import argparse
import time
import traceback
from pathlib import Path

from . import protocol as P
from .common import set_triton_cache, CommandLoop, gather_memory, init_distributed, parallel_context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--width", type=int, default=864)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args(argv)

    t_process = time.time()
    set_triton_cache(P.ROLE_TEACHER)
    loop = CommandLoop(P.ROLE_TEACHER)
    loop.connect()
    rank, world, device = init_distributed()

    import torch

    from taomate_h3 import teacher as teacher_module
    from taomate_h3.model.geometry import direct_5s_geometry
    from taomate_h3.model.pipeline import MiniMaxH3NativePipeline

    context = parallel_context(rank, world)
    loop.setup_groups()
    t_load = time.time()
    pipeline = MiniMaxH3NativePipeline(
        model_root=args.model_root,
        device=device,
        parallel_context=context,
        rank=rank,
        world_size=world,
        transformer_load_w8a8_policy=None,  # BF16 base H3 without LoRA, as teacher.py:420-427
    )
    geometry = direct_5s_geometry(width=args.width, height=args.height)
    torch.cuda.synchronize()
    pids = loop.rank_pids()  # collective: every rank reaches this line
    loop.send({"type": P.READY, "pids": pids, "load_s": time.time() - t_load,
               "process_to_ready_s": time.time() - t_process, "memory": gather_memory()})

    previous_clean = None
    previous_count: int | None = None
    next_local = 0
    while True:
        command = loop.next_command()
        kind = command["type"]
        if kind == P.SHUTDOWN:
            break
        if kind == P.RESET:
            previous_clean, previous_count, next_local = None, None, 0
            loop.send({"type": "reset_done", "session": int(command["session"])})  # audio tail dropped
            continue
        if kind != P.TEACH:
            continue
        session = int(command["session"])
        local = int(command["local_index"])
        try:
            if local != next_local:
                raise RuntimeError(f"teacher expected local request {next_local}, got {local}")
            torch.cuda.synchronize()
            t_start = time.time()
            with torch.no_grad():
                hidden, tags = pipeline._encode_text(prompt=command["prompt"].strip())
            features = (hidden.detach().to("cpu").contiguous(), tags.detach().to("cpu").contiguous())
            torch.cuda.synchronize()
            t_text = time.time()
            milestones, clean, active, receipt = teacher_module._generate_request(
                torch,
                pipeline=pipeline,
                geometry=geometry,
                text_features=features,
                audio_seed=int(command["seed"]) + local,  # teacher.py:440 audio_seed_base + index
                request_index=local,
                previous_clean=previous_clean,
                previous_audio_latent_count=previous_count,
            )
            torch.cuda.synchronize()
            t_done = time.time()
            previous_clean, previous_count, next_local = clean, active, local + 1
            if rank == 0:
                blob = P.pack_blob({
                    "text_hidden": features[0],
                    "text_tags": features[1],
                    "milestones": milestones,
                    "audio_latent_count": active,
                    "audio_noise_seed": int(command["seed"]) + local,
                    "receipt": receipt,
                })
                loop.send({
                    "type": P.TEACHER_DONE, "session": session,
                    "request_index": int(command["request_index"]), "local_index": local,
                    "t_start": t_start, "t_text_done": t_text, "t_done": t_done,
                    "text_tokens": int(features[0].shape[0]), "audio_latent_count": active,
                    "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
                    "blob": blob,
                })
        except Exception as exc:  # report and drop the session state; the adapter decides
            previous_clean, previous_count, next_local = None, None, 0
            loop.send({"type": P.ERROR, "session": session,
                       "request_index": command.get("request_index"),
                       "message": f"{type(exc).__name__}: {exc}",
                       "traceback": traceback.format_exc()})
    loop.flush()
    torch.distributed.barrier()
    torch.distributed.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
