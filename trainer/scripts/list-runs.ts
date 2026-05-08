#!/usr/bin/env bun
/**
 * trainings/<slug>/<v>/ 안의 run 인벤토리 출력.
 *
 * Usage:
 *   bun trainer/scripts/list-runs.ts <slug> [<version>]
 *
 * 출력: run_id, 시작 시각, weight 파일 수, 총 크기, env.snapshot 의 GPU/torch
 */

import { execSync } from "node:child_process";

const slug    = process.argv[2];
const version = process.argv[3]; // optional

if (!slug) {
  console.error("usage: bun list-runs.ts <slug> [<version>]");
  process.exit(1);
}

const prefix = version
  ? `s3://tu8qpqw6ag/trainings/${slug}/${version}/`
  : `s3://tu8qpqw6ag/trainings/${slug}/`;

const lsOut = execSync(
  `aws s3 ls --profile runpod --endpoint-url https://s3api-eu-ro-1.runpod.io --region eu-ro-1 --recursive ${prefix}`,
  { encoding: "utf8" },
);

// run_id 단위 그룹핑
const runs = new Map<string, { size: number; files: number; latest: string }>();
for (const line of lsOut.split("\n")) {
  const m = line.match(/^(\S+)\s+(\S+)\s+(\d+)\s+(.+)$/);
  if (!m) continue;
  const [, date, time, sizeStr, key] = m;
  const parts = key.split("/");
  // trainings/<slug>/<v>/<run_id>/...
  const runIdx = version ? 3 : 3;
  const runId = parts[runIdx];
  if (!runId) continue;
  const cur = runs.get(runId) ?? { size: 0, files: 0, latest: "" };
  cur.size  += Number(sizeStr);
  cur.files += 1;
  const ts = `${date} ${time}`;
  if (ts > cur.latest) cur.latest = ts;
  runs.set(runId, cur);
}

const sorted = [...runs.entries()].sort(([a], [b]) => (a < b ? 1 : -1));
console.log(`run_id`.padEnd(72) + ` | files | size      | latest`);
console.log("-".repeat(120));
for (const [runId, info] of sorted) {
  const sizeMb = (info.size / 1024 / 1024).toFixed(1) + " MB";
  console.log(
    runId.padEnd(72) + ` | ${String(info.files).padStart(5)} | ${sizeMb.padStart(9)} | ${info.latest}`,
  );
}
console.log(`\n${sorted.length} runs at ${prefix}`);
