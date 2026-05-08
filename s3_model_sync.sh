#!/bin/bash

# -------- 환경/프로필 --------
PROFILE="runpod"
REGION="eu-ro-1"
ENDPOINT="https://s3api-eu-ro-1.runpod.io"
BUCKET="tu8qpqw6ag"

export AWS_S3_MULTIPART_THRESHOLD=8MB
export AWS_S3_MULTIPART_CHUNKSIZE=16MB
export AWS_MAX_CONCURRENT_REQUESTS=2

aws s3 --profile $PROFILE --endpoint $ENDPOINT --region $REGION sync ./wan/loras/ s3://$BUCKET/loras/  \
  --cli-read-timeout 7200 \
  --cli-connect-timeout 7200 \
  --debug