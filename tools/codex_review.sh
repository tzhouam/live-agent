#!/usr/bin/env bash
# Run one Codex (GPT-6 Sol) review checkpoint with all material inlined in the prompt.
#
# Usage: tools/codex_review.sh <tag> <instructions.md> <file>...
#
# The Codex bwrap sandbox cannot start on this host (user namespaces are disabled:
# /proc/sys/user/max_user_namespaces = 0), and running Codex unsandboxed is not
# permitted. So the reviewer runs with `-s read-only` and gets every file it
# needs inline. Outputs go to docs/reviews/<tag>_{prompt.md,review.md,events.jsonl,meta.txt}.
set -euo pipefail
cd "$(dirname "$0")/.."
tag=$1; instr=$2; shift 2
out=docs/reviews
mkdir -p "$out"
prompt=$out/${tag}_prompt.md
{
  cat "$instr"
  echo
  echo "NOTE: your shell sandbox cannot start on this host, so file reads will fail. All material you need is inlined below. Each file is delimited by '===== FILE: <path> ====='."
  for f in "$@"; do
    echo
    echo "===== FILE: $f ====="
    cat "$f"
  done
} > "$prompt"

model=gpt-6-sol
set +e
timeout 2400 codex exec -m "$model" -s read-only --skip-git-repo-check --json \
  -o "$out/${tag}_review.md" - < "$prompt" > "$out/${tag}_events.jsonl" 2> "$out/${tag}_stderr.log"
rc=$?
set -e
tid=$(grep -o '"thread_id":"[^"]*"' "$out/${tag}_events.jsonl" | head -1 | cut -d'"' -f4 || true)
rollout=$( [ -n "$tid" ] && grep -rl "$tid" ~/.codex/sessions 2>/dev/null | head -1 || true)
{
  echo "tag: $tag"
  echo "date_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "repo_head: $(git rev-parse HEAD)"
  echo "repo_dirty_files: $(git status --porcelain | wc -l)"
  echo "vllm_omni_head: $(git -C external/vllm-omni rev-parse HEAD 2>/dev/null || echo n/a)"
  echo "codex_cli: $(codex --version 2>/dev/null | tail -1)"
  echo "requested_model: $model"
  echo "command: codex exec -m $model -s read-only --skip-git-repo-check --json -o $out/${tag}_review.md - < $prompt"
  echo "exit_code: $rc"
  echo "thread_id: $tid"
  echo "rollout: $rollout"
  echo "rollout_models: $( [ -n "$rollout" ] && grep -o '"model":"[^"]*"' "$rollout" | sort | uniq -c | tr '\n' ' ' )"
  echo "inlined_files: $*"
  echo "prompt_sha256: $(sha256sum "$prompt" | cut -d' ' -f1)"
} > "$out/${tag}_meta.txt"
cat "$out/${tag}_meta.txt"
