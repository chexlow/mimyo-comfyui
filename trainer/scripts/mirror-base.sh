#!/usr/bin/env bash
# 베이스 모델 한 번 mirror — 로컬에서 1회 실행하고 끝.
#
# Usage:
#   ./scripts/mirror-base.sh zimage-base
#   ./scripts/mirror-base.sh zimage-turbo
#   ./scripts/mirror-base.sh adapter-v2
#
# AWS profile 'runpod' 가 ~/.aws/config 에 설정되어 있다고 가정.
# 로컬 캐시는 trainer/runs/_bases/<name>/ 에 둔다 (gitignore).

set -euo pipefail

NAME="${1:-}"
[ -n "$NAME" ] || { echo "usage: $0 <zimage-base|zimage-turbo|adapter-v2>"; exit 1; }

BUCKET="tu8qpqw6ag"
PROFILE="runpod"
ENDPOINT="https://s3api-eu-ro-1.runpod.io"
REGION="eu-ro-1"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE_ROOT="$SCRIPT_DIR/../runs/_bases"
mkdir -p "$CACHE_ROOT"

case "$NAME" in
  zimage-base)
    HF_REPO="Tongyi-MAI/Z-Image"
    S3_PREFIX="bases/zimage-base"
    ;;
  zimage-turbo)
    HF_REPO="Tongyi-MAI/Z-Image-Turbo"
    S3_PREFIX="bases/zimage-turbo"
    ;;
  adapter-v2)
    HF_REPO="ostris/zimage_turbo_training_adapter"
    S3_PREFIX="bases/adapters/ostris-zimage-turbo-training-adapter-v2"
    ;;
  *)
    echo "unknown name: $NAME"; exit 1 ;;
esac

LOCAL_DIR="$CACHE_ROOT/$NAME"

echo "[1/3] downloading $HF_REPO  →  $LOCAL_DIR"
python3 - <<PY
from huggingface_hub import snapshot_download
import os
snapshot_download(
    repo_id="$HF_REPO",
    local_dir="$LOCAL_DIR",
    local_dir_use_symlinks=False,
    token=os.environ.get("HF_TOKEN"),
    max_workers=8,
)
PY

echo "[2/3] writing manifest"
cat > "$LOCAL_DIR/mirror_manifest.json" <<JSON
{
  "name": "$NAME",
  "hf_repo": "$HF_REPO",
  "downloaded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "s3_uri": "s3://$BUCKET/$S3_PREFIX/"
}
JSON

echo "[3/3] uploading to s3://$BUCKET/$S3_PREFIX/"
aws s3 --profile "$PROFILE" --endpoint-url "$ENDPOINT" --region "$REGION" \
    sync "$LOCAL_DIR/" "s3://$BUCKET/$S3_PREFIX/" \
    --exclude '.cache/*' \
    --exclude '.git/*'

echo "done."
echo "  s3 uri: s3://$BUCKET/$S3_PREFIX/"
