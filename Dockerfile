FROM runpod/worker-comfyui:5.1.0-base

# install custom nodes using comfy-cli
RUN comfy-node-install ComfyUI-Crystools comfyui_essentials ComfyUI-Impact-Pack ComfyUI-Custom-Scripts ComfyS3  

# Copy local static input files into the ComfyUI input directory (delete if not needed)
# Assumes you have an 'input' folder next to your Dockerfile
COPY input/ /comfyui/input/