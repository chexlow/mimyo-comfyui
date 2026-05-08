"""2단계 — _inbox/ 의 모든 처리 가능 이미지를 raw/ + curated/<bucket>/ 로 적재.

raw/ 는 원본 보존. curated/<bucket>/ 는:
  1) face-aware center crop (얼굴 위치 기준 정사각형. 실패시 image center)
  2) bucket size 로 LANCZOS downscale (upscale 안 함)

자동 격리(reject)는 하지 않는다. spec 미달(undersized / extreme aspect)도
진입시키되 `flags` 에 표시한다.
"""
from __future__ import annotations
import re
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from .paths import DatasetPaths, BUCKETS, MIN_SHORT_SIDE
from .report import load, update_stage


EXTREME_ASPECT_RATIO = 2.5  # long / short 가 이 이상이면 flag

_SAFE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, fallback: str = "src") -> str:
    s = _SAFE.sub("-", text.lower()).strip("-")
    return s or fallback


def _next_seq(raw_dir: Path) -> int:
    if not raw_dir.exists():
        return 1
    seen = []
    for p in raw_dir.glob("*"):
        m = re.match(r"^(\d{4})_", p.name)
        if m:
            seen.append(int(m.group(1)))
    return (max(seen) + 1) if seen else 1


def _ensure_dirs(paths: DatasetPaths) -> None:
    paths.raw.mkdir(parents=True, exist_ok=True)
    for b in BUCKETS:
        paths.bucket_dir(b).mkdir(parents=True, exist_ok=True)


def _square_crop_box(w: int, h: int, cx: float, cy: float) -> tuple[int, int, int, int]:
    """이미지 (w, h) 에서 (cx, cy) 중심의 정사각형 crop box. boundary clamp."""
    crop_size = min(w, h)
    half = crop_size / 2.0
    cx = max(half, min(w - half, cx))
    cy = max(half, min(h - half, cy))
    left = int(round(cx - half))
    top = int(round(cy - half))
    right = left + crop_size
    bottom = top + crop_size
    return left, top, right, bottom


def _save_normalized(
    src: Path,
    dst: Path,
    target_short: int,
    *,
    face_crop: bool,
    crop_enabled: bool,
) -> dict:
    """src 를 dst 에 normalize 해서 저장.

    face_crop=True  : InsightFace 로 얼굴 center 잡고 정사각형 crop
    face_crop=False : image center 로 정사각형 crop (crop_enabled=True 인 경우)
    crop_enabled=False: crop 안 함, short-side resize 만

    returns: {"size": (w, h), "resized": bool, "cropped": bool, "face_found": bool}
    """
    with Image.open(src) as im:
        if im.mode != "RGB":
            im = im.convert("RGB")
        w, h = im.size
        face_found = False

        if crop_enabled:
            if face_crop:
                from .face import detect_largest_from_path, face_center
                f = detect_largest_from_path(src)
                if f is not None:
                    cx, cy = face_center(f)
                    face_found = True
                else:
                    cx, cy = w / 2.0, h / 2.0
            else:
                cx, cy = w / 2.0, h / 2.0
            left, top, right, bottom = _square_crop_box(w, h, cx, cy)
            im = im.crop((left, top, right, bottom))
            cw, ch = im.size  # 정사각형
            cropped = True
        else:
            cw, ch = w, h
            cropped = False

        short_side = min(cw, ch)
        if short_side > target_short:
            im = im.resize((target_short, target_short) if cropped else
                           ((target_short, int(round(ch * target_short / cw))) if cw < ch
                            else (int(round(cw * target_short / ch)), target_short)),
                           Image.Resampling.LANCZOS)
            new_w, new_h = im.size
            resized = True
        else:
            new_w, new_h = cw, ch
            resized = False

        ext = dst.suffix.lower()
        if ext in {".jpg", ".jpeg"}:
            im.save(dst, "JPEG", quality=95, optimize=True)
        elif ext == ".webp":
            im.save(dst, "WEBP", quality=95, method=6)
        else:
            im.save(dst, "PNG", optimize=True)
        return {
            "size": (new_w, new_h),
            "resized": resized,
            "cropped": cropped,
            "face_found": face_found,
        }


def run(
    paths: DatasetPaths,
    *,
    source_tag: str = "inbox",
    face_crop: bool = True,
    crop_enabled: bool = True,
) -> dict:
    report = load(paths.report)
    probe = report.get("probe")
    if not probe:
        raise RuntimeError("probe stage has not run. Run `probe` first.")

    _ensure_dirs(paths)

    enterable = [r for r in probe["files"] if r.get("reject_reason") != "corrupt"]
    skipped_corrupt = [r for r in probe["files"] if r.get("reject_reason") == "corrupt"]

    seq = _next_seq(paths.raw)
    moved: list[dict] = []
    no_face_count = 0

    for row in enterable:
        src = paths.inbox / row["file"]
        if not src.exists():
            continue  # idempotent
        ext = src.suffix.lower()
        seq_str = f"{seq:04d}"

        original_size = row.get("size") or [0, 0]
        original_short = row.get("short_side", 0)
        original_long = max(original_size) if original_size else 0
        aspect = (original_long / original_short) if original_short else 1.0

        bucket = row["bucket"] if row.get("ok") else BUCKETS[0]

        flags: list[str] = []
        if not row.get("ok"):
            flags.append(row.get("reject_reason", "spec_miss"))
        if original_short and original_short < MIN_SHORT_SIDE:
            if "undersized" not in flags:
                flags.append("undersized")
        if aspect >= EXTREME_ASPECT_RATIO:
            flags.append(f"extreme_aspect_ratio_{aspect:.2f}")

        # raw/<seq>_<source>.<ext>
        raw_name = f"{seq_str}_{_slugify(source_tag)}{ext}"
        raw_path = paths.raw / raw_name
        shutil.copy2(src, raw_path)

        # curated/<bucket>/<seq>_pending.<ext> — face-aware crop + bucket resize
        cur_name = f"{seq_str}_pending{ext}"
        cur_path = paths.bucket_dir(bucket) / cur_name
        info = _save_normalized(
            src, cur_path, target_short=bucket,
            face_crop=face_crop, crop_enabled=crop_enabled,
        )
        if crop_enabled and face_crop and not info["face_found"]:
            flags.append("no_face_detected")
            no_face_count += 1

        src.unlink()  # raw/ 에 보존됨

        moved.append({
            "seq": seq_str, "bucket": bucket,
            "raw": str(raw_path.relative_to(paths.base)),
            "curated": str(cur_path.relative_to(paths.base)),
            "original_size": [int(original_size[0]), int(original_size[1])] if original_size else None,
            "curated_size": list(info["size"]),
            "resized": info["resized"],
            "cropped": info["cropped"],
            "face_found": info["face_found"],
            "flags": flags,
        })
        seq += 1

    payload = {
        "adopted": len(moved),
        "resized": sum(1 for m in moved if m.get("resized")),
        "cropped": sum(1 for m in moved if m.get("cropped")),
        "face_aware_crop": face_crop,
        "crop_enabled": crop_enabled,
        "no_face_detected": no_face_count,
        "with_flags": sum(1 for m in moved if m["flags"]),
        "skipped_corrupt": [r["file"] for r in skipped_corrupt],
        "moved": moved,
        "buckets": {
            str(b): sum(1 for m in moved if m["bucket"] == b)
            for b in BUCKETS
        },
    }
    update_stage(paths.report, paths.slug, paths.version, "curate", payload)

    print(f"[curate] adopted={len(moved)}  cropped={payload['cropped']}  resized={payload['resized']}  no_face={no_face_count}  flagged={payload['with_flags']}  skipped_corrupt={len(skipped_corrupt)}")
    for b in BUCKETS:
        n = payload["buckets"][str(b)]
        if n:
            print(f"  bucket {b}: {n}")
    if payload["with_flags"]:
        print(f"  ⚠ flagged (review _curation_report.json):")
        for m in moved:
            if m["flags"]:
                print(f"    - {m['curated']}  flags={m['flags']}  original={m.get('original_size')}  curated={m['curated_size']}")
    return payload
