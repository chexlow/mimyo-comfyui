"""1단계 — _inbox/ 안 이미지 검사. 해상도/포맷/깨짐 판정."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, UnidentifiedImageError

from .paths import DatasetPaths, MIN_SHORT_SIDE, SUPPORTED_EXTS, pick_bucket
from .report import update_stage


def _iter_inbox(paths: DatasetPaths) -> list[Path]:
    if not paths.inbox.exists():
        return []
    return sorted(
        p for p in paths.inbox.iterdir()
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXTS
        and not p.name.startswith(".")
    )


def run(paths: DatasetPaths) -> dict:
    files = _iter_inbox(paths)
    rows: list[dict] = []
    pass_count = 0
    fail_count = 0

    for f in files:
        rel = f.name
        try:
            with Image.open(f) as im:
                im.verify()
            with Image.open(f) as im:
                w, h = im.size
                fmt = (im.format or "").lower()
        except (UnidentifiedImageError, OSError) as e:
            rows.append({"file": rel, "ok": False, "reject_reason": "corrupt", "error": str(e)})
            fail_count += 1
            continue

        short_side = min(w, h)
        if short_side < MIN_SHORT_SIDE:
            rows.append({
                "file": rel, "ok": False,
                "reject_reason": "short_side_below_1024",
                "size": [w, h], "short_side": short_side, "format": fmt,
            })
            fail_count += 1
            continue

        rows.append({
            "file": rel, "ok": True,
            "size": [w, h], "short_side": short_side, "format": fmt,
            "bucket": pick_bucket(short_side),
        })
        pass_count += 1

    payload = {
        "inbox_total": len(files),
        "pass": pass_count,
        "fail": fail_count,
        "files": rows,
    }
    update_stage(paths.report, paths.slug, paths.version, "probe", payload)
    print(f"[probe] inbox={len(files)} pass={pass_count} fail={fail_count}")
    if fail_count:
        print(f"[probe] rejection reasons:")
        from collections import Counter
        reasons = Counter(r["reject_reason"] for r in rows if not r["ok"])
        for reason, n in reasons.most_common():
            print(f"  - {reason}: {n}")
    return payload
