#!/bin/bash

# Usage: ./deploy.sh [anime|real] [version]
# Example: ./deploy.sh real 0.0.1

MODE=$1
VERSION=$2

if [ -z "$MODE" ] || [ -z "$VERSION" ]; then
  echo "❌ Usage: ./deploy.sh [anime|real] [version]"
  echo "   Example: ./deploy.sh real 0.0.1"
  exit 1
fi

if [ "$MODE" != "anime" ] && [ "$MODE" != "real" ]; then
  echo "❌ Invalid mode. Use 'anime' or 'real'."
  exit 1
fi

DOCKERFILE="Dockerfile.$MODE"
IMAGE="actmkan/comfyui-worker:$MODE-$VERSION"

echo "===================================="
echo "📌 Deploying ComfyUI Worker"
echo "📦 Mode     : $MODE"
echo "🏷️ Version  : $VERSION"
echo "🐳 Image    : $IMAGE"
echo "📄 Dockerfile: $DOCKERFILE"
echo "===================================="

# Build (force platform linux/amd64)
echo "🚧 Building Docker image (platform: linux/amd64)..."
docker build \
  --platform=linux/amd64 \
  -f $DOCKERFILE \
  -t $IMAGE .
if [ $? -ne 0 ]; then
  echo "❌ Docker build failed."
  exit 1
fi

# Push
echo "🚀 Pushing Docker image..."
docker push $IMAGE
if [ $? -ne 0 ]; then
  echo "❌ Docker push failed."
  exit 1
fi

# Cleanup local image
echo "🧹 Removing local Docker image..."
docker rmi $IMAGE
if [ $? -ne 0 ]; then
  echo "⚠️ Warning: Failed to remove local image. It may not exist or is in use."
else
  echo "🗑️ Local image deleted: $IMAGE"
fi

echo "🎉 Done! Successfully deployed: $IMAGE"
