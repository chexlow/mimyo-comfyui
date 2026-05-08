"""_curation_report.json 읽기/쓰기."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save(path: Path, report: dict[str, Any]) -> None:
    report["updated_at"] = _now_iso()
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False))


def update_stage(path: Path, slug: str, version: str, stage: str, payload: dict[str, Any]) -> dict[str, Any]:
    report = load(path)
    report.setdefault("slug", slug)
    report.setdefault("version", version)
    report[stage] = {"ran_at": _now_iso(), **payload}
    save(path, report)
    return report
