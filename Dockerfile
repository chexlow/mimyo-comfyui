FROM runpod/worker-comfyui:5.5.1-base

# install custom nodes using comfy-cli
RUN comfy-node-install ComfyUI-Crystools comfyui_essentials comfyui-impact-pack comfyui-custom-scripts comfys3 comfyui-impact-subpack  

# Copy local static input files into the ComfyUI input directory (delete if not needed)
# Assumes you have an 'input' folder next to your Dockerfile
COPY input/ /comfyui/input/