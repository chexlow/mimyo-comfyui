#!/usr/bin/env bash
set -euo pipefail

# Usage: ./deploy.sh [version]
# Example: ./deploy.sh 0.0.2

VERSION="${1:-}"
IMAGE_REPO="${IMAGE_REPO:-actmkan/qwen3-vl-caption-it}"
MODEL_NAME="${MODEL_NAME:-prithivMLmods/Qwen3-VL-8B-Abliterated-Caption-it}"
BASE_PATH="${BASE_PATH:-/models}"
MODEL_DIR="${MODEL_DIR:-}"
LOCAL_MODEL_PATH="${LOCAL_MODEL_PATH:-/models/qwen3-vl-caption-it}"

if [[ -z "${VERSION}" ]]; then
  echo "Usage: $0 [version]"
  echo "Example: $0 0.0.2"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_DIR="${MODEL_DIR:-${SCRIPT_DIR}/model}"
IMAGE="${IMAGE_REPO}:${VERSION}"

if [[ ! -d "${MODEL_DIR}" ]]; then
  echo "Local model directory not found: ${MODEL_DIR}" >&2
  echo "Run: ${SCRIPT_DIR}/download-model.sh" >&2
  exit 1
fi

if ! find "${MODEL_DIR}" -type f -name "config.json" -print -quit | grep -q .; then
  echo "Local model directory does not look like a Hugging Face snapshot: ${MODEL_DIR}" >&2
  echo "Missing config.json. Run: ${SCRIPT_DIR}/download-model.sh" >&2
  exit 1
fi

if ! find "${MODEL_DIR}" -type f \( -name "*.safetensors" -o -name "*.bin" -o -name "*.pt" \) -print -quit | grep -q .; then
  echo "Local model directory has no model weight files: ${MODEL_DIR}" >&2
  echo "Expected one of: *.safetensors, *.bin, *.pt" >&2
  exit 1
fi

echo "===================================="
echo "Deploying Qwen3-VL Caption-it server"
echo "Version   : ${VERSION}"
echo "Image     : ${IMAGE}"
echo "Model     : ${MODEL_NAME}"
echo "Model dir : ${MODEL_DIR}"
echo "Dockerfile: ${SCRIPT_DIR}/Dockerfile"
echo "===================================="

echo "Building Docker image for linux/amd64..."
docker build \
  --platform=linux/amd64 \
  --build-context "local_model=${MODEL_DIR}" \
  --build-arg "LOCAL_MODEL_PATH=${LOCAL_MODEL_PATH}" \
  --build-arg "BASE_PATH=${BASE_PATH}" \
  -f "${SCRIPT_DIR}/Dockerfile" \
  -t "${IMAGE}" \
  "${SCRIPT_DIR}"

echo "Pushing Docker image..."
docker push "${IMAGE}"

echo "Removing local Docker image..."
if ! docker rmi "${IMAGE}"; then
  echo "Warning: failed to remove local image ${IMAGE}" >&2
fi

echo "Done: ${IMAGE}"
