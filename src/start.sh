#!/usr/bin/env bash

# Use libtcmalloc for better memory management
TCMALLOC="$(ldconfig -p | grep -Po "libtcmalloc.so.\d" | head -n 1)"
export LD_PRELOAD="${TCMALLOC}"

# Ensure ComfyUI-Manager runs in offline network mode inside the container
comfy-manager-set-mode offline || echo "worker-comfyui - Could not set ComfyUI-Manager network_mode" >&2

echo "worker-comfyui: Starting ComfyUI"

# Allow operators to tweak verbosity; default is DEBUG.
: "${COMFY_LOG_LEVEL:=DEBUG}"

# ComfyUI VRAM Management Mode
# https://docs.comfy.org/interface/settings/server-config#vram-management-mode
: "${COMFY_VRAM_MANAGEMENT_MODE:=auto}"
: "${COMFY_PROMPT_METADATA:=disabled}"
: "${COMFY_SERVER_CONFIG:=}"


# Serve the API and don't shutdown the container
if [ "$SERVE_API_LOCALLY" == "true" ]; then
    # python -u /comfyui/main.py --disable-auto-launch --disable-metadata --listen --verbose "${COMFY_LOG_LEVEL}" --log-stdout &
    comfy --workspace /comfyui launch -- \
        --disable-auto-launch ${COMFY_SERVER_CONFIG} \
        --verbose "${COMFY_LOG_LEVEL}" --log-stdout \
        --port 8188 \
        --listen \
        --cuda-device 0 &

    echo "worker-comfyui: Starting RunPod Handler"
    uv run python -u /handler.py --rp_serve_api --rp_api_host=0.0.0.0
else
    # python -u /comfyui/main.py --disable-auto-launch --disable-metadata --verbose "${COMFY_LOG_LEVEL}" --log-stdout &
    comfy --workspace /comfyui launch -- \
        --disable-auto-launch ${COMFY_SERVER_CONFIG} \
        --verbose "${COMFY_LOG_LEVEL}" --log-stdout \
        --port 8188 \
        --cuda-device 0 &

    echo "worker-comfyui: Starting RunPod Handler"
    uv run python -u /handler.py
fi