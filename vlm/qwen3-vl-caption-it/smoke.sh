#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: ENDPOINT=http://localhost:8000/v1/chat/completions MODEL=qwen3-vl-caption-it $0 <image-path>"
  exit 1
fi

ENDPOINT="${ENDPOINT:-http://localhost:8000/v1/chat/completions}"
MODEL="${MODEL:-qwen3-vl-caption-it}"
IMAGE_PATH="$1"
RUNPOD_API_KEY="${RUNPOD_API_KEY:-}"

python - "${ENDPOINT}" "${MODEL}" "${IMAGE_PATH}" "${RUNPOD_API_KEY}" <<'PY'
import base64
import json
import mimetypes
import pathlib
import sys
import urllib.request
from urllib.parse import urlparse

endpoint, model, image_path, runpod_api_key = sys.argv[1:5]
path = pathlib.Path(image_path)
mime = mimetypes.guess_type(path.name)[0] or "image/webp"
image_data = base64.b64encode(path.read_bytes()).decode("ascii")


def normalize_endpoint(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.netloc == "api.runpod.ai":
        base = raw.rstrip("/")
        if base.endswith("/openai/v1"):
            return f"{base}/chat/completions"
        if "/openai/v1/" not in base and not base.endswith("/chat/completions"):
            return f"{base}/openai/v1/chat/completions"
    if raw.rstrip("/").endswith("/v1"):
        return f"{raw.rstrip('/')}/chat/completions"
    return raw


endpoint = normalize_endpoint(endpoint)

payload = {
    "model": model,
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Describe this image as a concise natural-language prompt for image generation. "
                        "Focus on subject, pose, outfit, lighting, framing, background, and visual style."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_data}"},
                },
            ],
        }
    ],
    "temperature": 0.2,
    "max_tokens": 512,
}

request = urllib.request.Request(
    endpoint,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Content-Type": "application/json",
        **({"Authorization": f"Bearer {runpod_api_key}"} if runpod_api_key else {}),
    },
    method="POST",
)

with urllib.request.urlopen(request, timeout=300) as response:
    print(response.read().decode("utf-8"))
PY
