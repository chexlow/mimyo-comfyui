"""3단계 — perceptual hash 로 curated/ 안 중복 컷 감지.

자동 이동은 하지 않는다. 발견된 중복은 `_curation_report.json["dedup"]` 에
기록되고, 오빠가 보고 manual 로 정리한다.
"""
from __future__ import annotations
from pathlib import Path

import imagehash
from PIL import Image

from .paths import DatasetPaths, BUCKETS
from .report import update_stage


PHASH_DISTANCE_THRESHOLD = 5  # 이 미만이면 동일 컷으로 간주


def _all_curated(paths: DatasetPaths) -> list[Path]:
    files = []
    for b in BUCKETS:
        d = paths.bucket_dir(b)
        if d.exists():
            files.extend(sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}))
    return files


def run(paths: DatasetPaths) -> dict:
    files = _all_curated(paths)
    hashes: list[tuple[Path, imagehash.ImageHash]] = []
    for f in files:
        with Image.open(f) as im:
            h = imagehash.phash(im)
        hashes.append((f, h))

    # greedy: 첫 번째를 anchor 로, 그 뒤 거리 < threshold 면 duplicate flag
    anchors: list[tuple[Path, imagehash.ImageHash]] = []
    duplicate_pairs: list[dict] = []
    for f, h in hashes:
        dup_of = None
        for af, ah in anchors:
            d = h - ah
            if d < PHASH_DISTANCE_THRESHOLD:
                dup_of = (af, d)
                break
        if dup_of is None:
            anchors.append((f, h))
        else:
            af, d = dup_of
            duplicate_pairs.append({
                "file": str(f.relative_to(paths.base)),
                "duplicate_of": str(af.relative_to(paths.base)),
                "phash_distance": int(d),
            })

    payload = {
        "checked": len(files),
        "unique_anchors": len(anchors),
        "duplicates_found": len(duplicate_pairs),
        "duplicates": duplicate_pairs,
        "threshold": PHASH_DISTANCE_THRESHOLD,
        "note": "duplicates are flagged for review, not auto-removed",
    }
    update_stage(paths.report, paths.slug, paths.version, "dedup", payload)
    print(f"[dedup] checked={len(files)}  unique={len(anchors)}  duplicates_flagged={len(duplicate_pairs)}")
    for d in duplicate_pairs:
        print(f"  ⚠ {d['file']}  ≈ {d['duplicate_of']}  (phash distance {d['phash_distance']})")
    return payload
