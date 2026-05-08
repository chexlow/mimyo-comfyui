#!/usr/bin/env bash
# Pod entrypoint — 한 번 실행되고 끝난다.
# 흐름: env 검증 → 데이터셋/베이스 sync → ai-toolkit 학습 → 산출물 push → exit

set -euo pipefail

log()  { printf '[trainer %s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
fail() { log "ERROR: $*"; exit 1; }

# ---------- 1. env 검증 ----------
required=(
  DATASET_SLUG
  DATASET_VERSION
  CONFIG_NAME
  BASE_MODEL
  RUN_ID
  TRIGGER_TOKEN
  S3_ENDPOINT
  S3_BUCKET
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_REGION
)
for v in "${required[@]}"; do
  [ -n "${!v:-}" ] || fail "required env not set: $v"
done

log "RUN_ID=$RUN_ID"
log "dataset=$DATASET_SLUG/$DATASET_VERSION  config=$CONFIG_NAME  base=$BASE_MODEL"
log "GPU info:"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv || true

CONFIG_SRC="/workspace/configs/${CONFIG_NAME}.yaml"
[ -f "$CONFIG_SRC" ] || fail "config not found: $CONFIG_SRC"

DATASET_DIR="/workspace/dataset"
BASE_DIR="/workspace/base"
OUTPUT_DIR="/workspace/output"
SAMPLE_DIR="$OUTPUT_DIR/samples"
mkdir -p "$DATASET_DIR" "$BASE_DIR" "$OUTPUT_DIR" "$SAMPLE_DIR"

# AWS CLI 공통 옵션 (RunPod S3-compatible endpoint)
AWS=(aws s3 --endpoint-url "$S3_ENDPOINT" --region "$AWS_REGION")

# ---------- 2. 데이터셋 sync ----------
DATASET_S3="s3://$S3_BUCKET/datasets/faces/$DATASET_SLUG/$DATASET_VERSION/curated/"
log "syncing dataset  ${DATASET_S3}  →  ${DATASET_DIR}/"
"${AWS[@]}" sync "$DATASET_S3" "$DATASET_DIR/" \
    --exclude '.gitkeep' \
    --no-progress
DATASET_COUNT=$(find "$DATASET_DIR" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webp' \) | wc -l | tr -d ' ')
log "dataset image count: $DATASET_COUNT"
[ "$DATASET_COUNT" -gt 0 ] || fail "dataset is empty after sync"

# ---------- 3. 베이스 모델 sync ----------
# BASE_MODEL 이름을 prefix 로 매핑
case "$BASE_MODEL" in
  zimage-base|zimage-turbo)
    BASE_S3="s3://$S3_BUCKET/bases/$BASE_MODEL/"
    ;;
  *)
    fail "unknown BASE_MODEL: $BASE_MODEL"
    ;;
esac
log "syncing base  ${BASE_S3}  →  ${BASE_DIR}/"
"${AWS[@]}" sync "$BASE_S3" "$BASE_DIR/" --no-progress

# 추론 검증용 turbo 도 같이 가져옴 (sample step 에서 필요할 수 있음)
TURBO_DIR="/workspace/turbo"
mkdir -p "$TURBO_DIR"
"${AWS[@]}" sync "s3://$S3_BUCKET/bases/zimage-turbo/" "$TURBO_DIR/" --no-progress || true

# ---------- 4. config 변수 치환 ----------
RUNTIME_CONFIG="/workspace/runtime-config.yaml"
export DATASET_DIR BASE_DIR OUTPUT_DIR SAMPLE_DIR TRIGGER_TOKEN RUN_ID
envsubst < "$CONFIG_SRC" > "$RUNTIME_CONFIG"
log "runtime config:"
sed 's/^/  /' "$RUNTIME_CONFIG"

# ---------- 5. 학습 실행 ----------
TRAIN_LOG="$OUTPUT_DIR/training.log"
log "launching ai-toolkit"
( cd /opt/ai-toolkit && python run.py "$RUNTIME_CONFIG" 2>&1 | tee -a "$TRAIN_LOG" ) || {
  TRAIN_RC=$?
  log "training exited with rc=$TRAIN_RC — pushing partial output for diagnosis"
  push_output_partial=true
}

# ---------- 6. 스냅샷 ----------
cp "$RUNTIME_CONFIG" "$OUTPUT_DIR/config.snapshot.yaml"
{
  echo "{"
  echo "  \"run_id\": \"$RUN_ID\","
  echo "  \"dataset_slug\": \"$DATASET_SLUG\","
  echo "  \"dataset_version\": \"$DATASET_VERSION\","
  echo "  \"config_name\": \"$CONFIG_NAME\","
  echo "  \"base_model\": \"$BASE_MODEL\","
  echo "  \"trigger_token\": \"$TRIGGER_TOKEN\","
  echo "  \"started_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"gpu\": \"$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)\","
  echo "  \"torch\": \"$(python -c 'import torch;print(torch.__version__)')\","
  echo "  \"cuda\": \"$(python -c 'import torch;print(torch.version.cuda)')\""
  echo "}"
} > "$OUTPUT_DIR/env.snapshot.json"

# ---------- 7. 산출물 push ----------
TRAINING_S3="s3://$S3_BUCKET/trainings/$DATASET_SLUG/$DATASET_VERSION/$RUN_ID/"
log "pushing output  ${OUTPUT_DIR}/  →  ${TRAINING_S3}"
"${AWS[@]}" sync "$OUTPUT_DIR/" "$TRAINING_S3" --no-progress

log "done. RUN_ID=$RUN_ID"
log "output: $TRAINING_S3"

# pod 는 RunPod 측 lifecycle (terminateAfter / one-shot pod) 으로 자동 종료
exit 0
