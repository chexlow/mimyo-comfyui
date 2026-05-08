#!/bin/bash

# -------- 공통 설정 --------
PROFILE="runpod"
REGION="eu-ro-1"
ENDPOINT="https://s3api-eu-ro-1.runpod.io"
BUCKET="niiet2wzky"

# 사용법:
#   ./s3-list-usage.sh           -> 버킷 전체
#   ./s3-list-usage.sh models/   -> models/ 이하만
PREFIX="$1"   # 인자로 prefix 받기 (없으면 전체)

MAX_KEYS=1000

echo "== List objects =="
if [ -z "$PREFIX" ]; then
  echo "  s3://$BUCKET (전체)"
else
  echo "  s3://$BUCKET/$PREFIX"
fi
echo

CONT_TOKEN=""
TOTAL_BYTES=0
TOTAL_OBJECTS=0

while true; do
  if [ -z "$CONT_TOKEN" ]; then
    if [ -z "$PREFIX" ]; then
      RESP=$(aws s3api list-objects-v2 \
        --profile "$PROFILE" \
        --endpoint-url "$ENDPOINT" \
        --region "$REGION" \
        --bucket "$BUCKET" \
        --max-keys $MAX_KEYS)
    else
      RESP=$(aws s3api list-objects-v2 \
        --profile "$PROFILE" \
        --endpoint-url "$ENDPOINT" \
        --region "$REGION" \
        --bucket "$BUCKET" \
        --prefix "$PREFIX" \
        --max-keys $MAX_KEYS)
    fi
  else
    if [ -z "$PREFIX" ]; then
      RESP=$(aws s3api list-objects-v2 \
        --profile "$PROFILE" \
        --endpoint-url "$ENDPOINT" \
        --region "$REGION" \
        --bucket "$BUCKET" \
        --max-keys $MAX_KEYS \
        --continuation-token "$CONT_TOKEN")
    else
      RESP=$(aws s3api list-objects-v2 \
        --profile "$PROFILE" \
        --endpoint-url "$ENDPOINT" \
        --region "$REGION" \
        --bucket "$BUCKET" \
        --prefix "$PREFIX" \
        --max-keys $MAX_KEYS \
        --continuation-token "$CONT_TOKEN")
    fi
  fi

  # KeyCount가 없거나 0이면 끝
  COUNT=$(echo "$RESP" | jq '.KeyCount // 0')
  if [ "$COUNT" -eq 0 ]; then
    break
  fi

  # 각 파일: size(byte) \t key
  echo "$RESP" | jq -r '.Contents[] | "\(.Size)\t\(.Key)"'

  # 이번 페이지 합산
  PAGE_SUM=$(echo "$RESP" | jq '[.Contents[].Size] | add // 0')
  TOTAL_BYTES=$((TOTAL_BYTES + PAGE_SUM))
  TOTAL_OBJECTS=$((TOTAL_OBJECTS + COUNT))

  # 다음 토큰 준비
  CONT_TOKEN=$(echo "$RESP" | jq -r '.NextContinuationToken // empty')
  if [ -z "$CONT_TOKEN" ]; then
    break
  fi
done

echo
echo "== Total =="
TOTAL_GIB=$(awk -v b="$TOTAL_BYTES" 'BEGIN { printf "%.2f", b/1024/1024/1024 }')

echo "Total objects : $TOTAL_OBJECTS"
echo "Total bytes   : $TOTAL_BYTES"
echo "Total GiB     : $TOTAL_GIB GiB"

if [ "$TOTAL_OBJECTS" -eq 0 ]; then
  echo
  echo "⚠️  이 prefix 아래에는 객체가 없는 것으로 보임."
  echo "   - 버킷 루트 전체를 보고 싶으면:   ./s3-list-usage.sh"
  echo "   - models/ 이하만 보고 싶으면:    ./s3-list-usage.sh models/"
fi
