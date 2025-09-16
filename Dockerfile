FROM runpod/worker-comfyui:5.1.0-base

# install custom nodes using comfy-cli
RUN comfy-node-install comfyui-kjnodes comfyui_essentials ComfyUI-Impact-Pack ComfyUI-Custom-Scripts ComfyS3  

# download models using comfy-cli
# the "--filename" is what you use in your ComfyUI workflow
RUN comfy model download --url https://civitai.com/api/download/models/2044887?type=Model&format=SafeTensor&size=pruned&fp=fp16 --relative-path models/checkpoints --filename one20obsession155.Kdef.safetensors
RUN comfy model download --url https://huggingface.co/stabilityai/control-lora/resolve/main/control-LoRAs-rank256/control-lora-canny-rank256.safetensors --relative-path models/controlnet --filename control-lora-canny-rank256.safetensors

# Copy local static input files into the ComfyUI input directory (delete if not needed)
# Assumes you have an 'input' folder next to your Dockerfile
COPY input/ /comfyui/input/