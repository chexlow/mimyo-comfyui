# mimyo-curate

face 데이터셋 큐레이션 파이프라인. `_inbox/` 에 떨궈놓은 이미지를 spec 에
맞춰 `raw/`, `curated/<bucket>/`, `captions.jsonl`, `manifest.json` 까지
자동으로 만들어낸다.

## 흐름

```
_inbox/  →  probe  →  curate  →  dedup  →  face-check  →  caption  →  finalize
                                                              ↑
                                          Ollama qwen3-vl:4b (localhost:11434)
```

각 단계는 idempotent — 재실행해도 결과 같다. 실패하거나 중간에 멈춰도
그 단계만 다시 돌리면 된다.

## 설치

[uv](https://docs.astral.sh/uv/) 권장:

```bash
cd datasets/_scripts/curate
uv sync
```

또는 pip:

```bash
cd datasets/_scripts/curate
pip install -e .
```

## 사용

```bash
# 1) 오빠가 _inbox 에 이미지 떨궈놓는다
cp ~/Downloads/*.png datasets/faces/synth_aria/v1/_inbox/

# 2) 단계별 실행
uv run mimyo-curate probe       --slug synth_aria --version v1
uv run mimyo-curate curate      --slug synth_aria --version v1
uv run mimyo-curate dedup       --slug synth_aria --version v1
uv run mimyo-curate face-check  --slug synth_aria --version v1
uv run mimyo-curate caption     --slug synth_aria --version v1 --trigger m1my0_aria
uv run mimyo-curate finalize    --slug synth_aria --version v1

# 또는 한번에
uv run mimyo-curate all --slug synth_aria --version v1 --trigger m1my0_aria
```

## 단계 정의

| # | 단계 | 입력 | 출력 |
|---|---|---|---|
| 1 | `probe` | `_inbox/` | `_curation_report.json["probe"]` (해상도/포맷/깨진파일 검사) |
| 2 | `curate` | `_inbox/` 의 처리 가능 이미지 전부 | `raw/<seq>_<src>.<ext>` + `curated/<bucket>/<seq>_pending.<ext>` (spec 미달도 진입, flag 만 표시) |
| 3 | `dedup` | `curated/` | 중복 컷 발견 → flag (자동 이동 X) |
| 4 | `face-check` | `curated/` | InsightFace 임베딩 + cosine 매트릭스 → outlier flag (자동 이동 X) |
| 5 | `caption` | `curated/` | sidecar `.txt` + `captions.jsonl` (Ollama qwen3-vl) |
| 6 | `finalize` | 전부 | `manifest.json` 갱신 + 다양성 매트릭스 |

## 자동 격리 정책 — 안 함

이 파이프라인은 **자동으로 이미지를 빼지 않는다**. `_inbox/` 에 떨궈놓은
이미지는 `corrupt` (PIL 못 여는 깨진 파일) 만 빼고 모두 `raw/` + `curated/`
로 진입한다. 의심스러운 컷은 `_curation_report.json` 에 flag 로 기록되고,
오빠가 보고 manual 로 결정한다.

flag 사유:

- `undersized` — short side < 1024 (학습 효과 약하지만 진입은 됨)
- `duplicate` — 다른 컷과 perceptual hash distance < 5
- `face_outlier` — 얼굴 임베딩이 medoid 와 cosine < 0.45
- (caption 단계) `identity_attribute_detected` / `too_short` / `too_long` 등

진짜로 빼고 싶으면 `curated/<bucket>/` 또는 `raw/` 에서 직접 삭제하거나
다른 곳으로 옮긴다.

## 의존성 / 환경

- Python 3.11+
- Ollama 데몬 + `qwen3-vl:4b` 모델 (`ollama pull qwen3-vl:4b`)
- InsightFace 첫 실행 시 모델 자동 다운로드 (~300MB, `~/.insightface/`)
