#!/usr/bin/env bash
# Reproduce the TaoMate-H3 environment used for M0 (2026-09-26). CPU-only; no GPU needed.
#
# Differences from the TaoMate-H3 README (torch 2.8 + vllm 0.11.1 + FA3 built from source):
# * vllm==0.11.1 pins torch 2.9.0+cu128, so uv resolves torch 2.9.0 (README says 2.8).
# * FlashAttention-3 is not built from source (the host only has a CUDA 13 toolkit). We use
#   the prebuilt Hopper build from HF kernels-community/flash-attn3 (revision 7cb368cf,
#   kernel sha 8a730d9, variant torch-stable-abi29-cu128) already present in the shared HF
#   cache, exposed under the upstream module name `flash_attn_interface` by a 3-line shim.
# * The clone external/TaoMate-H3 (6b2f998) is put on sys.path with a .pth file instead of
#   `pip install -e`, so the read-only clone is never written to.
# * /usr/local/bin/ffmpeg lacks libx264; /usr/bin/ffmpeg (4.4.2) has it. A PATH shim dir
#   .venvs/taomate-h3/ffbin holds symlinks to /usr/bin/ffmpeg and /usr/bin/ffprobe.
set -euo pipefail
cd "$(dirname "$0")/../.."
REPO=$PWD
export UV_CACHE_DIR=$REPO/.cache/uv
VENV=$REPO/.venvs/taomate-h3
uv venv --python 3.11 "$VENV"
uv pip install --python "$VENV/bin/python" --torch-backend cu128 \
  "vllm==0.11.1" "diffusers==0.35.2" "transformers==4.57.6" "tokenizers==0.22.1" einops \
  "huggingface-hub>=0.34" numpy Pillow PyYAML "safetensors>=0.4.5" pyzmq pytest torchvision
SP=$("$VENV/bin/python" -c "import site; print(site.getsitepackages()[0])")
FA3=/data/models/hub/kernels--kernels-community--flash-attn3/snapshots/7cb368cf8278b583132eb72cbf312d54586df2e2/build/torch-stable-abi29-cu128-x86_64-linux
rm -rf "$SP/flash_attn3_kc" && cp -rL "$FA3" "$SP/flash_attn3_kc"
cat > "$SP/flash_attn_interface.py" <<'EOF'
# live-agent shim: exposes the prebuilt kernels-community FA3 (Hopper, stable ABI, cu128;
# HF kernels-community/flash-attn3 rev 7cb368cf, kernel sha 8a730d9) under the upstream
# FA3 module name `flash_attn_interface` that TaoMate-H3 imports.
from flash_attn3_kc.flash_attn_interface import *  # noqa: F401,F403
from flash_attn3_kc.flash_attn_interface import flash_attn_func, flash_attn_varlen_func  # noqa: F401
EOF
echo "$REPO/external/TaoMate-H3/src" > "$SP/taomate_h3_src.pth"
echo "$REPO" > "$SP/live_agent_repo.pth"
mkdir -p "$VENV/ffbin"
ln -sf /usr/bin/ffmpeg "$VENV/ffbin/ffmpeg"
ln -sf /usr/bin/ffprobe "$VENV/ffbin/ffprobe"
# public TaoMate-H3 LoRA (HF TaoLiveAIGC/TaoMate-H3, sha 7d7a51f3)
HF_HOME=$REPO/.cache/hf "$VENV/bin/python" -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='TaoLiveAIGC/TaoMate-H3', local_dir='$REPO/.cache/models/TaoMate-H3',
                  allow_patterns=['config.json', 'adapter_config.json', 'adapter_model.safetensors'])"
"$VENV/bin/python" -c "import torch, vllm, flash_attn_interface, taomate_h3; print(torch.__version__, vllm.__version__)"
