"""InsightFace 공통 유틸 — face detection / embedding."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np


@lru_cache(maxsize=1)
def get_app() -> Any:
    """InsightFace FaceAnalysis 싱글턴. 첫 호출은 모델 다운로드 (~300MB)."""
    from insightface.app import FaceAnalysis
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app


def detect_largest(image_bgr: np.ndarray) -> Any | None:
    """가장 큰 얼굴 1개 반환. 없으면 None."""
    app = get_app()
    faces = app.get(image_bgr)
    if not faces:
        return None
    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
    return faces[0]


def detect_largest_from_path(path: Path) -> Any | None:
    """이미지 파일에서 가장 큰 얼굴 1개. 없거나 파일 못 읽으면 None."""
    import cv2
    img = cv2.imread(str(path))
    if img is None:
        return None
    return detect_largest(img)


def face_center(face: Any) -> tuple[float, float]:
    bbox = face.bbox
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
