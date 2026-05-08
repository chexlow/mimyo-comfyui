#!/usr/bin/env bun
/**
 * 학습 산출물을 production loras/ 로 명시적 promote.
 *
 * Usage:
 *   bun trainer/scripts/promote.ts <run_id> --weight final --tag synth_aria-v1
 *
 *   trainings/<slug>/<v>/<run_id>/weights/<weight>.safetensors
 *     → loras/<tag>.safetensors
 *
 * 자동화하지 않는다 — 학습 결과를 직접 본 다음에만 promote 한다.
 */

import { execSync } from "node:child_process";
import { parseArgs } from "node:util";

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    weight:  { type: "string", default: "final" },
    tag:     { type: "string" },
    "dry-run": { type: "boolean", default: false },
  },
});

const runId = positionals[0];
if (!runId) {
  console.error("usage: bun promote.ts <run_id> --weight final --tag <name>");
  process.exit(1);
}
const tag = values.tag;
if (!tag) {
  console.error("--tag required");
  process.exit(1);
}

// run_id 의 컨벤션: <dataset_v>__<config>__<ts>__<sha>
// 슬러그는 RunPod 에서 직접 못 끌어오니 launch 시 기록한 인벤토리(list-runs.ts) 또는
// run_id 를 다 적어주는 것을 가정. 1차에선 명시적으로 받는다.
const slug    = process.env.SLUG    ?? promptStdin("dataset slug (e.g. synth_aria): ");
const version = process.env.VERSION ?? runId.split("__")[0];

const SRC = `s3://tu8qpqw6ag/trainings/${slug}/${version}/${runId}/weights/${values.weight}.safetensors`;
const DST = `s3://tu8qpqw6ag/loras/${tag}.safetensors`;

console.log(`promote: ${SRC}  →  ${DST}`);
if (values["dry-run"]) {
  console.log("[dry-run] no copy");
  process.exit(0);
}

const cmd = [
  "aws", "s3", "cp",
  "--profile", "runpod",
  "--endpoint-url", "https://s3api-eu-ro-1.runpod.io",
  "--region", "eu-ro-1",
  SRC, DST,
].map((s) => (/\s/.test(s) ? `'${s}'` : s)).join(" ");

execSync(cmd, { stdio: "inherit" });
console.log("done.");

function promptStdin(label: string): string {
  process.stdout.write(label);
  const buf = new Uint8Array(1024);
  // bun 의 동기 stdin 읽기
  const n = (Bun as any).file("/dev/stdin").readSync?.(buf) ?? 0;
  return new TextDecoder().decode(buf.subarray(0, n)).trim();
}
