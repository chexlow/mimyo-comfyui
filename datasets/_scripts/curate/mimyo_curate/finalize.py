"""6단계 — manifest.json 갱신 + 다양성 매트릭스 집계."""
from __future__ import annotations
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .paths import DatasetPaths, BUCKETS
from .report import update_stage


# 캡션에서 자동 추출하는 다양성 축 (단순 키워드 기반 — vision 모델 출력 표준화 못 했으므로)
ANGLE_KEYWORDS = {
    "frontal":       [r"\bfrontal\b", r"\bfacing (the )?camera\b", r"\bfront view\b"],
    "three_quarter": [r"\bthree[- ]quarter\b", r"\b3/4\b"],
    "profile":       [r"\bside profile\b", r"\bprofile view\b"],
    "back":          [r"\bback view\b", r"\bfrom behind\b"],
}
DISTANCE_KEYWORDS = {
    "close_up":         [r"\bclose[- ]up\b"],
    "head_shoulders":   [r"\bhead[- ]and[- ]shoulders\b", r"\bportrait\b"],
    "upper_body":       [r"\bupper body\b", r"\bbust\b", r"\bwaist[- ]up\b"],
    "full_body":        [r"\bfull body\b", r"\bfull[- ]length\b"],
}


def _classify(caption: str, table: dict[str, list[str]]) -> str:
    text = caption.lower()
    for label, patterns in table.items():
        for p in patterns:
            if re.search(p, text):
                return label
    return "unknown"


def run(paths: DatasetPaths) -> dict:
    # captions.jsonl 읽기
    rows: list[dict] = []
    if paths.captions_jsonl.exists():
        for line in paths.captions_jsonl.read_text().splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    # bucket 별 count
    bucket_counts: Counter[int] = Counter()
    for b in BUCKETS:
        d = paths.bucket_dir(b)
        if d.exists():
            n = sum(1 for p in d.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
            bucket_counts[b] = n

    image_count = sum(bucket_counts.values())

    # 다양성 매트릭스 (캡션 기반 자동 추정)
    angle_counts: Counter[str] = Counter()
    distance_counts: Counter[str] = Counter()
    for r in rows:
        cap = r.get("caption") or ""
        angle_counts[_classify(cap, ANGLE_KEYWORDS)] += 1
        distance_counts[_classify(cap, DISTANCE_KEYWORDS)] += 1

    # manifest.json 갱신
    manifest_path = paths.manifest
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        "subject_slug": paths.slug,
        "subject_type": "face",
        "dataset_version": paths.version,
    }
    manifest["image_count"] = image_count
    manifest["resolution_buckets"] = [
        {"short_side": b, "count": bucket_counts[b]}
        for b in BUCKETS if bucket_counts[b] > 0
    ]
    manifest["caption_format"] = manifest.get("caption_format", "natural_language")
    manifest["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    payload = {
        "image_count": image_count,
        "buckets": {str(b): bucket_counts[b] for b in BUCKETS},
        "diversity": {
            "angle":    dict(angle_counts),
            "distance": dict(distance_counts),
        },
        "needs_review": sum(1 for r in rows if r.get("qa_status") == "needs_review"),
    }
    update_stage(paths.report, paths.slug, paths.version, "finalize", payload)

    print(f"[finalize] image_count={image_count}")
    print(f"  buckets:  {dict(bucket_counts)}")
    print(f"  angle:    {dict(angle_counts)}")
    print(f"  distance: {dict(distance_counts)}")
    print(f"  needs_review: {payload['needs_review']}")
    return payload
