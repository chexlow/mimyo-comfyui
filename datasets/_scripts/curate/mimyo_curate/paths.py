"""슬러그/버전 → 경로 헬퍼."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    # datasets/_scripts/curate/mimyo_curate/paths.py → repo root 4단계 위
    return Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class DatasetPaths:
    slug: str
    version: str
    root: Path

    @property
    def base(self) -> Path:
        return self.root / "datasets" / "faces" / self.slug / self.version

    @property
    def inbox(self) -> Path:
        return self.base / "_inbox"

    @property
    def rejected(self) -> Path:
        return self.base / "_inbox" / "_rejected"

    @property
    def raw(self) -> Path:
        return self.base / "raw"

    @property
    def curated(self) -> Path:
        return self.base / "curated"

    def bucket_dir(self, bucket: int) -> Path:
        return self.curated / str(bucket)

    @property
    def manifest(self) -> Path:
        return self.base / "manifest.json"

    @property
    def captions_jsonl(self) -> Path:
        return self.base / "captions.jsonl"

    @property
    def report(self) -> Path:
        return self.base / "_curation_report.json"


def for_dataset(slug: str, version: str = "v1") -> DatasetPaths:
    paths = DatasetPaths(slug=slug, version=version, root=_repo_root())
    if not paths.base.exists():
        raise FileNotFoundError(f"dataset base not found: {paths.base}")
    return paths


# 큐레이션 spec 상수
BUCKETS = (1024, 1280, 1536)
MIN_SHORT_SIDE = 1024
SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def pick_bucket(short_side: int) -> int:
    """short side 에 가장 가까운 (이하인) bucket 반환."""
    candidates = [b for b in BUCKETS if b <= short_side]
    return max(candidates) if candidates else BUCKETS[0]
