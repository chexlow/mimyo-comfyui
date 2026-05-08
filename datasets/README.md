# Datasets

mimyo 데이터셋 보관소. 이미지 본체는 git 이 아닌 S3
(`s3://tu8qpqw6ag/datasets/`) 에 동기화하고, 메타데이터만 git 으로 추적한다.

> 이 디렉토리는 **데이터셋 자체**만 다룬다. 학습(trainer / hyperparam / weight 산출물 /
> training history)은 본 디렉토리의 책임이 아니며 별도 영역에서 관리한다.

## 디렉토리 구조

```
datasets/
  faces/
    <slug>/
      v<n>/
        manifest.json              # public 메타 (git 추적)
        manifest.private.json      # private 메타 (git 제외)
        README.md                  # 데이터셋 가이드 / 큐레이션 룰
        raw/                       # 원본 백업 (git 제외, S3 동기화)
        curated/                   # 큐레이션된 이미지 (git 제외, S3 동기화)
          1024/ 1280/ 1536/        # short-side resolution bucket
        captions.jsonl             # 캡션 + 검수 상태 (git 제외)
        _example/                  # reference layout (git 추적, 학습 미사용)
  _index.json                      # subject 인덱스
```

각 데이터셋 버전 안에 있는 `_example/` 디렉토리는 같은 슬러그의 `raw/` / `curated/` /
`captions.jsonl` / `manifest.private.json` 이 어떤 형태여야 하는지를 placeholder
이미지와 sidecar / jsonl 샘플로 미러링해 두는 git 추적 reference 다. 학습에 사용되지
않으며, 실제 입력은 `raw/` 와 `curated/` 다. 명명 규칙과 sidecar / jsonl 스키마는
`<slug>/v<n>/_example/README.md` 를 참조한다.

## 버전 정책

- **데이터셋 버전 (`v1`, `v2` …)**: `raw/` 또는 `curated/` 가 의미 있게 바뀌면 증가
- 데이터셋 버전은 학습 산출물 버전과 무관하게 매겨진다. 같은 `v1` 데이터셋이 여러 학습 시도에 쓰일 수 있다

## Trigger token 컨벤션

`m1my0_<short>` (예: `m1my0_aria`). 이 토큰은 캡션 본문에 박혀 데이터셋의 일부가 된다.

- `m1my0_` prefix 로 흔한 단어와의 충돌 방지 (실존 인물 / 잘 알려진 캐릭터일수록 중요)
- slug 는 lowercase, 영숫자/언더스코어만
- subject_class 가 `synthetic` 인 경우 슬러그도 `synth_<name>` 형태로 명시 권장

## 캡션 원칙

캡션은 데이터셋 자체의 일부다. 포맷은 `manifest.json` 의 `caption_format` 으로 명시한다.

- 자연어 문장으로 작성한다. booru 태그 형식은 사용하지 않는다
- **가변 속성만** 캡션에 포함: 의상, 표정, 조명, 배경, 거리, 자세, 액션
- **인물 고유 특징은 캡션에서 뺀다**: 눈/입/얼굴형/머리 색 등은 trigger token 이 흡수하도록
- 트리거는 문장 첫머리에: `m1my0_aria, a young woman wearing a white dress, soft natural light, looking at camera`

## Subject class

`manifest.json` 의 `subject_class` 로 데이터의 성격을 명시한다.

| value | 의미 | consent 권장값 |
|---|---|---|
| `synthetic` | 합성 도구로 생성한 가상 인물 | `synthetic_subject` |
| `real_consented` | 실존 인물, 명시적 동의 받음 | `written_consent` |
| `public_dataset` | 공개 라이선스 데이터셋에서 가져옴 | `public_license` |

위 셋 중 어느 것에도 해당하지 않으면 데이터셋을 만들지 않는다.

## 민감 데이터 처리

- `license` 기본값은 `internal_only`. 외부 공개 결정이 별도로 있기 전까지 유지
- 실명 / 출처 / 외부 URL 등은 `manifest.private.json` 에만 두고 git 에서 제외한다
- public manifest 만 보고도 "어떤 인물인지" 식별되지 않도록 slug 는 약어 사용

## S3 동기화 (예정)

`scripts/dataset/sync.sh` 에서 처리할 예정. 기본 흐름:

```
aws s3 sync ./datasets/faces/<slug>/  s3://tu8qpqw6ag/datasets/faces/<slug>/ \
    --exclude 'manifest.json' --exclude 'README.md' \
    --exclude '.gitkeep' --exclude '_example/*'
```

manifest / README 는 git 에서, raw / curated / captions 는 S3 에서 source of truth.
