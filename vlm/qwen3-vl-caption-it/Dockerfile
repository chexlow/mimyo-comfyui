FROM runpod/worker-v1-vllm@sha256:2352429297d31351f42d7fbb34c66b5c2b0e75f40f2e8788951f3723d861d6f7

ARG LOCAL_MODEL_PATH="/models/qwen3-vl-caption-it"
ARG BASE_PATH="/models"

ENV MODEL_NAME="${LOCAL_MODEL_PATH}" \
    TOKENIZER_NAME="${LOCAL_MODEL_PATH}" \
    OPENAI_SERVED_MODEL_NAME_OVERRIDE="qwen3-vl-caption-it" \
    BASE_PATH="${BASE_PATH}" \
    HF_HOME="${BASE_PATH}/huggingface-cache/hub" \
    HUGGINGFACE_HUB_CACHE="${BASE_PATH}/huggingface-cache/hub" \
    HF_DATASETS_CACHE="${BASE_PATH}/huggingface-cache/datasets" \
    DTYPE="half" \
    MAX_MODEL_LEN="4096" \
    MAX_NUM_SEQS="4" \
    GPU_MEMORY_UTILIZATION="0.90" \
    LIMIT_MM_PER_PROMPT="image=1,video=0" \
    MM_PROCESSOR_CACHE_GB="0" \
    ENABLE_PREFIX_CACHING="true" \
    TRUST_REMOTE_CODE="true" \
    OMP_NUM_THREADS="1" \
    TOKENIZERS_PARALLELISM="false" \
    RAYON_NUM_THREADS="4"

RUN python3 -m pip install --no-cache-dir --upgrade hf_xet qwen-vl-utils==0.0.14

COPY --from=local_model . ${LOCAL_MODEL_PATH}/

RUN python3 - <<'PY'
import json
import os

model_path = os.environ["MODEL_NAME"]
with open("/local_model_args.json", "w") as f:
    json.dump(
        {
            "MODEL_NAME": model_path,
            "TOKENIZER_NAME": model_path,
            "DTYPE": os.environ.get("DTYPE", "half"),
        },
        f,
    )
PY
