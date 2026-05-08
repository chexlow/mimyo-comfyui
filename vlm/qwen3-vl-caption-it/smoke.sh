#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: ENDPOINT=https://api.runpod.ai/v2/<endpoint-id> MODEL=qwen3-vl-caption-it $0 <image-path>"
  exit 1
fi

ENDPOINT="${ENDPOINT:-http://localhost:8000/v1/chat/completions}"
MODEL="${MODEL:-qwen3-vl-caption-it}"
IMAGE_PATH="$1"
RUNPOD_API_KEY="${RUNPOD_API_KEY:-}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-5}"
POLL_TIMEOUT_SECONDS="${POLL_TIMEOUT_SECONDS:-900}"

python - "${ENDPOINT}" "${MODEL}" "${IMAGE_PATH}" "${RUNPOD_API_KEY}" "${POLL_INTERVAL_SECONDS}" "${POLL_TIMEOUT_SECONDS}" <<'PY'
import base64
import json
import mimetypes
import pathlib
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

endpoint, model, image_path, runpod_api_key, poll_interval, poll_timeout = sys.argv[1:7]
poll_interval = int(poll_interval)
poll_timeout = int(poll_timeout)
path = pathlib.Path(image_path)
mime = mimetypes.guess_type(path.name)[0] or "image/webp"
image_data = base64.b64encode(path.read_bytes()).decode("ascii")


def is_runpod_endpoint(raw: str) -> bool:
    return urlparse(raw).netloc == "api.runpod.ai"


def normalize_openai_endpoint(raw: str) -> str:
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


openai_payload = {
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


def request_json(url: str, payload: dict | None = None, timeout: int = 300) -> dict:
    headers = {
        "Content-Type": "application/json",
        **({"Authorization": f"Bearer {runpod_api_key}"} if runpod_api_key else {}),
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} from {url}: {body}") from e


def print_result(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))
    output = result.get("output", result)
    if isinstance(output, list):
        output = output[-1] if output else {}
    if isinstance(output, dict):
        choices = output.get("choices")
        if choices and isinstance(choices, list):
            content = choices[0].get("message", {}).get("content")
            if content:
                print("\n--- caption ---")
                print(content)


if is_runpod_endpoint(endpoint):
    base = endpoint.rstrip("/")
    submit_payload = {
        "input": {
            "openai_route": "/v1/chat/completions",
            "openai_input": openai_payload,
        }
    }
    submitted = request_json(f"{base}/run", submit_payload)
    print(json.dumps(submitted, ensure_ascii=False, indent=2))

    job_id = submitted.get("id")
    if not job_id:
        raise RuntimeError(f"RunPod /run response did not include a job id: {submitted}")

    deadline = time.time() + poll_timeout
    while time.time() < deadline:
        status = request_json(f"{base}/status/{job_id}", None, timeout=60)
        state = status.get("status")
        if state in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            print_result(status)
            if state != "COMPLETED":
                raise SystemExit(1)
            raise SystemExit(0)
        print(f"status={state}; waiting {poll_interval}s...", file=sys.stderr)
        time.sleep(poll_interval)

    raise TimeoutError(f"Timed out waiting for RunPod job {job_id}")

print_result(request_json(normalize_openai_endpoint(endpoint), openai_payload))
PY
