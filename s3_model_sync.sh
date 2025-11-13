#!/bin/bash

# -------- 환경/프로필 --------
PROFILE="runpod"
REGION="eu-ro-1"
ENDPOINT="https://s3api-eu-ro-1.runpod.io"
BUCKET="niiet2wzky"

aws s3 --profile $PROFILE --endpoint $ENDPOINT --region $REGION sync ./models/ s3://$BUCKET/models/  --debug --cli-read-timeout 7200
