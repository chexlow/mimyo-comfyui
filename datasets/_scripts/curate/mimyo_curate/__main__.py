"""mimyo-curate CLI."""
from __future__ import annotations
import click

from . import probe as _probe
from . import curate as _curate
from . import dedup as _dedup
from . import face_check as _face_check
from . import caption as _caption
from . import finalize as _finalize
from .paths import for_dataset


def _common(f):
    f = click.option("--slug", required=True, help="dataset slug, e.g. synth_aria")(f)
    f = click.option("--version", default="v1", show_default=True)(f)
    return f


@click.group()
def cli() -> None:
    """mimyo-curate — face dataset curation pipeline."""


@cli.command()
@_common
def probe(slug: str, version: str) -> None:
    paths = for_dataset(slug, version)
    _probe.run(paths)


@cli.command()
@_common
@click.option("--source-tag", default="inbox", show_default=True, help="raw/<seq>_<tag>.<ext> 의 tag")
@click.option("--no-face-crop", is_flag=True, default=False, help="얼굴 위치 무시하고 image center 로 crop")
@click.option("--no-crop", is_flag=True, default=False, help="crop 안 함, short-side resize 만")
def curate(slug: str, version: str, source_tag: str, no_face_crop: bool, no_crop: bool) -> None:
    paths = for_dataset(slug, version)
    _curate.run(
        paths,
        source_tag=source_tag,
        face_crop=not no_face_crop,
        crop_enabled=not no_crop,
    )


@cli.command()
@_common
def dedup(slug: str, version: str) -> None:
    paths = for_dataset(slug, version)
    _dedup.run(paths)


@cli.command("face-check")
@_common
@click.option("--threshold", default=0.45, show_default=True, type=float)
def face_check(slug: str, version: str, threshold: float) -> None:
    paths = for_dataset(slug, version)
    _face_check.run(paths, threshold=threshold)


@cli.command()
@_common
@click.option("--trigger", required=True, help="trigger token, e.g. m1my0_aria")
@click.option("--provider", type=click.Choice(["ollama", "florence"]), default="florence", show_default=True)
@click.option("--model", default=None, help="provider 별 default 사용 (ollama: qwen3-vl:4b / florence: thwri/CogFlorence-2-Large-Freeze)")
@click.option("--parallel", default=4, show_default=True, type=int, help="동시 호출 수 (ollama 만 적용)")
@click.option("--force", is_flag=True, default=False, help="기존 sidecar 캐시 무시하고 재캡션")
@click.option("--no-strip-hair", is_flag=True, default=False, help="hair 식별 속성 자동 제거 비활성화")
def caption(slug: str, version: str, trigger: str, provider: str, model: str | None, parallel: int, force: bool, no_strip_hair: bool) -> None:
    paths = for_dataset(slug, version)
    _caption.run(paths, trigger=trigger, provider=provider, model=model, parallel=parallel, force=force, strip_hair=not no_strip_hair)


@cli.command()
@_common
def finalize(slug: str, version: str) -> None:
    paths = for_dataset(slug, version)
    _finalize.run(paths)


@cli.command()
@_common
@click.option("--trigger", required=True, help="trigger token")
@click.option("--source-tag", default="inbox", show_default=True)
@click.option("--provider", type=click.Choice(["ollama", "florence"]), default="florence", show_default=True)
@click.option("--model", default=None, help="caption 모델. provider 별 default 사용")
@click.option("--face-threshold", default=0.45, show_default=True, type=float)
@click.option("--parallel", default=4, show_default=True, type=int, help="caption 동시 호출 수 (ollama 만)")
@click.option("--no-face-crop", is_flag=True, default=False)
@click.option("--no-crop", is_flag=True, default=False)
@click.option("--force-recaption", is_flag=True, default=False)
@click.option("--no-strip-hair", is_flag=True, default=False, help="hair 식별 속성 자동 제거 비활성화")
def all(slug: str, version: str, trigger: str, source_tag: str, provider: str, model: str | None,
        face_threshold: float, parallel: int, no_face_crop: bool, no_crop: bool, force_recaption: bool,
        no_strip_hair: bool) -> None:
    """전체 6단계 순차 실행."""
    paths = for_dataset(slug, version)
    _probe.run(paths)
    _curate.run(paths, source_tag=source_tag, face_crop=not no_face_crop, crop_enabled=not no_crop)
    _dedup.run(paths)
    _face_check.run(paths, threshold=face_threshold)
    _caption.run(paths, trigger=trigger, provider=provider, model=model, parallel=parallel, force=force_recaption, strip_hair=not no_strip_hair)
    _finalize.run(paths)


if __name__ == "__main__":
    cli()
