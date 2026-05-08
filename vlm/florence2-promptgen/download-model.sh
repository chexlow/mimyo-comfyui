#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

MODEL_NAME="${MODEL_NAME:-MiaoshouAI/Florence-2-base-PromptGen-v2.0}"
MODEL_REVISION="${MODEL_REVISION:-main}"
MODEL_BASENAME="${MODEL_NAME##*/}"
MODEL_DIR="${MODEL_DIR:-${REPO_ROOT}/models/new/LLM/${MODEL_BASENAME}}"

echo "===================================="
echo "Downloading local Florence2 model"
echo "Model    : ${MODEL_NAME}"
echo "Revision : ${MODEL_REVISION}"
echo "Target   : ${MODEL_DIR}"
echo "===================================="

python3 - "${MODEL_NAME}" "${MODEL_REVISION}" "${MODEL_DIR}" <<'PY'
import pathlib
import sys

model_name, revision, model_dir = sys.argv[1:4]

try:
    from huggingface_hub import snapshot_download
except ModuleNotFoundError:
    print(
        "huggingface_hub is not installed. Run:\n"
        "  python3 -m pip install --user --upgrade huggingface_hub hf_xet",
        file=sys.stderr,
    )
    raise SystemExit(2)

target = pathlib.Path(model_dir)
target.mkdir(parents=True, exist_ok=True)

snapshot_download(
    repo_id=model_name,
    revision=revision or None,
    local_dir=str(target),
    local_dir_use_symlinks=False,
)

print(f"Downloaded to {target}")
PY
