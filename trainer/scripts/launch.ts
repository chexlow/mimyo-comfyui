#!/usr/bin/env bun
/**
 * RunPod GraphQL API 로 학습 pod 생성 + env 주입.
 *
 * Usage:
 *   bun trainer/scripts/launch.ts \
 *     --slug synth_aria \
 *     --version v1 \
 *     --config zimage-face-lokr-smoke \
 *     --base zimage-base \
 *     --trigger m1my0_aria
 *
 * 필수 env (로컬):
 *   RUNPOD_API_KEY     — RunPod 콘솔에서 생성
 *   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY  — runpod profile 자격증명
 *
 * 선택 env:
 *   TRAINER_IMAGE      — 기본 actmkan/mimyo-trainer:latest
 *   GPU_TYPE_ID        — RunPod GPU type id, 기본 "RTX PRO 4500"
 */

import { execSync } from "node:child_process";
import { parseArgs } from "node:util";

const RUNPOD_GQL = "https://api.runpod.io/graphql";

const { values: args } = parseArgs({
  options: {
    slug:    { type: "string" },
    version: { type: "string" },
    config:  { type: "string" },
    base:    { type: "string", default: "zimage-base" },
    trigger: { type: "string" },
    gpu:     { type: "string", default: process.env.GPU_TYPE_ID ?? "RTX PRO 4500" },
    image:   { type: "string", default: process.env.TRAINER_IMAGE ?? "actmkan/mimyo-trainer:latest" },
    "stop-after": { type: "string", default: "8h" },
    "dry-run":    { type: "boolean", default: false },
  },
});

function need(key: keyof typeof args, label: string): string {
  const v = args[key];
  if (typeof v !== "string" || v.length === 0) {
    console.error(`missing --${label}`);
    process.exit(1);
  }
  return v;
}

const slug    = need("slug", "slug");
const version = need("version", "version");
const config  = need("config", "config");
const trigger = need("trigger", "trigger");
const gpu     = need("gpu", "gpu");
const image   = need("image", "image");
const base    = String(args.base);

const RUNPOD_API_KEY = process.env.RUNPOD_API_KEY;
if (!RUNPOD_API_KEY) {
  console.error("RUNPOD_API_KEY not set");
  process.exit(1);
}

// AWS 자격증명을 로컬 profile 에서 추출 (~/.aws/credentials 의 [runpod] 섹션)
function awsCred(key: "aws_access_key_id" | "aws_secret_access_key"): string {
  const v = execSync(`aws configure get ${key} --profile runpod`, { encoding: "utf8" }).trim();
  if (!v) throw new Error(`aws profile 'runpod' missing ${key}`);
  return v;
}

const AWS_ACCESS_KEY_ID     = awsCred("aws_access_key_id");
const AWS_SECRET_ACCESS_KEY = awsCred("aws_secret_access_key");

// run_id = <dataset_v>__<config-slug>__<UTC>__<git-sha7>
const ts     = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "").replace("T", "T").slice(0, 15) + "Z";
const sha    = execSync("git rev-parse --short=7 HEAD", { encoding: "utf8" }).trim();
const runId  = `${version}__${config.replace(/^zimage-face-/, "")}__${ts}__${sha}`;

const podEnv: Record<string, string> = {
  DATASET_SLUG:          slug,
  DATASET_VERSION:       version,
  CONFIG_NAME:           config,
  BASE_MODEL:            base,
  RUN_ID:                runId,
  TRIGGER_TOKEN:         trigger,
  S3_ENDPOINT:           "https://s3api-eu-ro-1.runpod.io",
  S3_BUCKET:             "tu8qpqw6ag",
  AWS_ACCESS_KEY_ID,
  AWS_SECRET_ACCESS_KEY,
  AWS_REGION:            "eu-ro-1",
  ...(process.env.HF_TOKEN ? { HF_TOKEN: process.env.HF_TOKEN } : {}),
};

const podName = `mimyo-trainer-${slug}-${version}-${ts}`;

const mutation = `
mutation DeployTrainer($input: PodFindAndDeployOnDemandInput!) {
  podFindAndDeployOnDemand(input: $input) {
    id
    name
    desiredStatus
    machine { gpuDisplayName }
  }
}`;

const variables = {
  input: {
    cloudType:          "COMMUNITY",
    gpuCount:           1,
    gpuTypeId:          gpu,
    name:               podName,
    imageName:          image,
    containerDiskInGb:  120,
    volumeInGb:         0,
    minVcpuCount:       8,
    minMemoryInGb:      32,
    dockerArgs:         "",
    ports:              "",
    env: Object.entries(podEnv).map(([key, value]) => ({ key, value })),
    // 학습 길어져도 안전하게 종료
    // RunPod 의 "stopAfter" 는 별도 mutation 에서 지원. 1차에선 entrypoint exit 후 수동 terminate.
  },
};

if (args["dry-run"]) {
  console.log("[dry-run] pod payload:");
  console.log(JSON.stringify(
    { name: podName, image, gpu, runId, env: { ...podEnv, AWS_SECRET_ACCESS_KEY: "<redacted>", AWS_ACCESS_KEY_ID: "<redacted>" } },
    null, 2,
  ));
  process.exit(0);
}

console.log(`launching pod ${podName} (run_id=${runId})…`);

const res = await fetch(RUNPOD_GQL, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${RUNPOD_API_KEY}`,
  },
  body: JSON.stringify({ query: mutation, variables }),
});

const json = (await res.json()) as { data?: any; errors?: Array<{ message: string }> };
if (json.errors && json.errors.length > 0) {
  console.error("RunPod GraphQL errors:");
  for (const e of json.errors) console.error("  -", e.message);
  process.exit(1);
}

const pod = json.data?.podFindAndDeployOnDemand;
if (!pod?.id) {
  console.error("unexpected response:", JSON.stringify(json, null, 2));
  process.exit(1);
}

console.log("pod created:");
console.log(`  id:      ${pod.id}`);
console.log(`  name:    ${pod.name}`);
console.log(`  status:  ${pod.desiredStatus}`);
console.log(`  gpu:     ${pod.machine?.gpuDisplayName ?? "(pending)"}`);
console.log(`  run_id:  ${runId}`);
console.log(`  output:  s3://tu8qpqw6ag/trainings/${slug}/${version}/${runId}/`);
