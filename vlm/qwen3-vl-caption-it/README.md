# Qwen3-VL Caption-it RunPod Serving

RunPod에서 `prithivMLmods/Qwen3-VL-8B-Abliterated-Caption-it`를 OpenAI-compatible image caption endpoint로 띄우는 최소 패키지입니다.

목표는 앱 통합 전에 먼저 서빙 안정성, latency, caption 품질만 확인하는 것입니다.
Serverless cold start에서 Hugging Face 다운로드가 반복되지 않도록 모델은 Docker image에 bake-in 합니다.

## Runtime

- Model: `prithivMLmods/Qwen3-VL-8B-Abliterated-Caption-it`
- Server: RunPod `worker-v1-vllm` Serverless worker
- Base image: `runpod/worker-v1-vllm:v2.14.0` linux/amd64 digest pinned
- API: OpenAI-compatible `/openai/v1`
- Default served model name: `qwen3-vl-caption-it`
- Suggested GPU: RunPod A40 48GB

A40 기준으로 `DTYPE=half`를 기본값으로 둡니다. H100 같은 BF16/FP8 실험 환경에서는 env로 바꿔서 테스트하세요.

## Build

기존 `mimyo-comfyui` RunPod worker와 동일하게 Docker Hub `actmkan` 네임스페이스를 기본값으로 둡니다.

먼저 모델을 로컬에 받습니다. 기본 위치는 `vlm/qwen3-vl-caption-it/model`이고 Git에서는 무시됩니다.

```bash
./vlm/qwen3-vl-caption-it/download-model.sh
```

`huggingface_hub`가 로컬 Python에 없으면 먼저 설치합니다.

```bash
python3 -m pip install --user --upgrade huggingface_hub hf_xet
```

그 다음 모델 디렉터리를 Docker named build context로 넣어 bake-in 이미지를 만듭니다.

```bash
./vlm/qwen3-vl-caption-it/deploy.sh 0.0.2
```

기본 image:

```text
actmkan/qwen3-vl-caption-it:0.0.2
```

다른 repository로 push해야 하면 `IMAGE_REPO`만 바꿉니다.

```bash
IMAGE_REPO="actmkan/qwen3-vl-caption-it" \
./vlm/qwen3-vl-caption-it/deploy.sh 0.0.2
```

로컬 build만 확인할 때:

```bash
docker build \
  --platform=linux/amd64 \
  --build-context local_model=./vlm/qwen3-vl-caption-it/model \
  --build-arg LOCAL_MODEL_PATH="/models/qwen3-vl-caption-it" \
  --build-arg BASE_PATH="/models" \
  -t actmkan/qwen3-vl-caption-it:local \
  vlm/qwen3-vl-caption-it
```

RunPod에서 쓰려면 이 이미지를 Docker Hub 또는 GHCR 같은 registry에 push한 뒤 RunPod Serverless endpoint의 container image로 지정합니다.

## RunPod Serverless Endpoint

권장 시작값:

```text
Type: Queue-based Serverless vLLM worker
GPU: A40 48GB
Disk: baked model image pull을 고려해 50GB 이상
```

환경 변수:

```text
MODEL_NAME=/models/qwen3-vl-caption-it
TOKENIZER_NAME=/models/qwen3-vl-caption-it
OPENAI_SERVED_MODEL_NAME_OVERRIDE=qwen3-vl-caption-it
BASE_PATH=/models
HF_HOME=/models/huggingface-cache/hub
HUGGINGFACE_HUB_CACHE=/models/huggingface-cache/hub
HF_DATASETS_CACHE=/models/huggingface-cache/datasets
DTYPE=half
MAX_MODEL_LEN=4096
MAX_NUM_SEQS=4
GPU_MEMORY_UTILIZATION=0.90
LIMIT_MM_PER_PROMPT=image=1,video=0
MM_PROCESSOR_CACHE_GB=0
ENABLE_PREFIX_CACHING=true
TRUST_REMOTE_CODE=true
OMP_NUM_THREADS=1
```

기동 중 CUDA graph나 메모리 이슈가 있으면 먼저 다음 값을 추가해서 다시 시도합니다.

```text
ENFORCE_EAGER=true
```

## Smoke Test

Serverless endpoint가 뜬 뒤 RunPod endpoint base URL을 `ENDPOINT`로 넘깁니다.

RunPod Serverless vLLM endpoint를 쓸 때는 endpoint base URL만 넘기면 됩니다. 스크립트가 `/openai/v1/chat/completions`를 자동으로 붙입니다.

```bash
RUNPOD_API_KEY="<runpod-api-key>" \
ENDPOINT="https://api.runpod.ai/v2/<endpoint-id>" \
MODEL="qwen3-vl-caption-it" \
./vlm/qwen3-vl-caption-it/smoke.sh ./sample.webp
```

Pod HTTP URL을 직접 열어둔 경우에는 기존 OpenAI-compatible path를 그대로 넘겨도 됩니다.

```bash
ENDPOINT="https://<runpod-url>/v1/chat/completions" \
MODEL="qwen3-vl-caption-it" \
./vlm/qwen3-vl-caption-it/smoke.sh ./sample.webp
```

직접 curl:

```bash
curl -X POST "https://api.runpod.ai/v2/<endpoint-id>/openai/v1/chat/completions" \
  -H "Authorization: Bearer <runpod-api-key>" \
  -H "Content-Type: application/json" \
  --data '{
    "model": "qwen3-vl-caption-it",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Describe this image as a concise natural-language prompt for image generation. Focus on subject, pose, outfit, lighting, framing, background, and visual style."
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/webp;base64,..."
            }
          }
        ]
      }
    ],
    "temperature": 0.2,
    "max_tokens": 512
  }'
```

## App Integration Later

앱에서는 이 서버를 직접 RunPod image generation workflow와 섞지 말고, 별도 caption client로 붙이는 편이 좋습니다.

```text
image buffer
-> caption endpoint
-> prompt text
-> existing RunPod image/video call
```

필요한 env 이름은 다음 단계에서 정합니다.

```text
RUNPOD_VLM_CAPTION_URL=https://api.runpod.ai/v2/<endpoint-id>/openai/v1/chat/completions
RUNPOD_VLM_CAPTION_MODEL=qwen3-vl-caption-it
```
