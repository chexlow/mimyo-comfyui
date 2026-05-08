"""4단계 — InsightFace 로 단일 인물 일관성 검증. 자동 reject 안 함, flag 만."""
from __future__ import annotations
from pathlib import Path

import cv2
import numpy as np

from .face import get_app
from .paths import DatasetPaths, BUCKETS
from .report import update_stage


# medoid 기준 cosine 이 이 미만이면 outlier 후보로 flag
OUTLIER_COSINE_THRESHOLD = 0.45


def _all_curated(paths: DatasetPaths) -> list[Path]:
    files = []
    for b in BUCKETS:
        d = paths.bucket_dir(b)
        if d.exists():
            files.extend(sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}))
    return files


def _embed(app, path: Path) -> np.ndarray | None:
    img = cv2.imread(str(path))
    if img is None:
        return None
    faces = app.get(img)
    if not faces:
        return None
    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
    return np.asarray(faces[0].normed_embedding, dtype=np.float32)


def run(paths: DatasetPaths, threshold: float = OUTLIER_COSINE_THRESHOLD) -> dict:
    files = _all_curated(paths)
    if not files:
        print("[face-check] no curated files")
        return {"checked": 0, "outliers": []}

    app = get_app()
    embs: list[tuple[Path, np.ndarray]] = []
    no_face: list[str] = []
    for f in files:
        e = _embed(app, f)
        if e is None:
            no_face.append(str(f.relative_to(paths.base)))
            continue
        embs.append((f, e))

    if len(embs) < 2:
        payload = {"checked": len(files), "with_face": len(embs), "no_face": no_face,
                   "outliers": [], "note": "too few faces for consistency check"}
        update_stage(paths.report, paths.slug, paths.version, "face_check", payload)
        print(f"[face-check] checked={len(files)} faces={len(embs)} no_face={len(no_face)}")
        return payload

    matrix = np.stack([e for _, e in embs])
    cos_sum = matrix @ matrix.T
    n = len(embs)
    mean_self_excl = (cos_sum.sum(axis=1) - np.diag(cos_sum)) / (n - 1)
    medoid_idx = int(np.argmax(mean_self_excl))
    medoid_cos = cos_sum[medoid_idx]

    outliers: list[dict] = []
    for i, (f, _) in enumerate(embs):
        if i == medoid_idx:
            continue
        c = float(medoid_cos[i])
        if c < threshold:
            outliers.append({"file": str(f.relative_to(paths.base)), "cosine_to_medoid": round(c, 3)})

    overall_mean = float((cos_sum.sum() - np.trace(cos_sum)) / (n * (n - 1)))
    payload = {
        "checked": len(files),
        "with_face": len(embs),
        "no_face": no_face,
        "medoid_file": str(embs[medoid_idx][0].relative_to(paths.base)),
        "mean_pairwise_cosine": round(overall_mean, 3),
        "outliers": outliers,
        "threshold": threshold,
        "note": "outliers are flagged for review, not auto-rejected",
    }
    update_stage(paths.report, paths.slug, paths.version, "face_check", payload)
    print(f"[face-check] checked={len(files)} faces={len(embs)} no_face={len(no_face)}")
    print(f"  mean_pairwise_cosine={overall_mean:.3f}  medoid={payload['medoid_file']}")
    print(f"  outliers (review): {len(outliers)}")
    for o in outliers:
        print(f"    - {o['file']}  cos={o['cosine_to_medoid']}")
    return payload
