# `_example/` — reference layout

이 디렉토리는 `synth_aria` v1 의 **파일 형태 / 명명 규칙 / sidecar 구조**를
보여주기 위한 git 추적 샘플이다. 실제 데이터셋의 `raw/`, `curated/`,
`captions.jsonl`, `manifest.private.json` 은 git 에서 제외되고 S3 가
source of truth 인데, 그것만으로는 어떤 형태인지 새로 들어온 사람이 알기
어렵기 때문에 같은 구조를 미러링해 둔다.

`_example/` 는 학습에 사용되지 않는다. 학습 입력은 항상 형제 디렉토리인
`raw/` 와 `curated/` 다.

## 들어 있는 파일

```
_example/
├── README.md                        # 이 문서
├── _generate_placeholders.py        # placeholder PNG 재생성 스크립트
├── manifest.private.example.json    # private 메타 템플릿
├── captions.example.jsonl           # captions.jsonl 한 줄당 형식 예시
├── raw/
│   ├── 0001_session-a.png           # 원본 백업 (placeholder)
│   └── 0002_session-a.png
└── curated/
    ├── 1024/
    │   └── 0003_park-fullbody.{png,txt}
    ├── 1280/
    │   ├── 0001_frontal-portrait.{png,txt}
    │   ├── 0002_cafe-threequarter.{png,txt}
    │   ├── 0004_bookstore-laugh.{png,txt}
    │   └── 0006_kitchen-cooking.{png,txt}
    └── 1536/
        └── 0005_studio-neutral.{png,txt}
```

## 명명 규칙

| 위치 | 형식 | 예 |
|---|---|---|
| raw | `<4digit-seq>_<source-tag>.<ext>` | `raw/0001_session-a.png` |
| curated | `<bucket>/<4digit-seq>_<scene-slug>.<ext>` | `curated/1280/0002_cafe-threequarter.png` |
| sidecar | curated 이미지와 같은 파일명에 `.txt` | `curated/1280/0002_cafe-threequarter.txt` |

- **seq** 는 raw 와 curated 가 **공유**한다. 즉 curated `0002` 는 raw `0002`
  에서 큐레이션된 것이라는 뜻. 같은 seq 에서 여러 crop 을 뽑으면
  `0002a`, `0002b` 처럼 suffix 를 붙인다.
- **source-tag** 는 촬영/생성 세션을 묶는 라벨. (`session-a`,
  `session-b`, `2026-05-04` 같은 식으로 자유롭게)
- **scene-slug** 는 다양성 축이 한눈에 보이게 짧은 영문 슬러그로
  (`frontal-portrait`, `cafe-threequarter`, `bookstore-laugh`).
- **bucket** 은 short-side 픽셀값. 이미지의 짧은 변 크기에 맞춰 분류.

## sidecar 캡션 (.txt)

curated 이미지마다 같은 이름의 `.txt` 파일을 둔다. 한 파일 안에 단일
자연어 캡션이 들어간다. ComfyUI / Kohya 계열 트레이너의 표준 입력 형태다.

캡션 작성 규칙은 상위 `datasets/README.md` 의 "캡션 원칙" 참고. 핵심:

- 트리거 토큰을 문장 첫머리에
- 가변 속성(의상, 표정, 조명, 배경, 거리, 자세)만 묘사
- 인물 고유 특징은 적지 않음

## captions.jsonl 형식

`captions.example.jsonl` 의 각 행은 다음 스키마다.

```ts
{
  "file":      string,   // v<n>/ 기준 상대 경로 (curated/<bucket>/<name>.png)
  "caption":   string,   // sidecar .txt 와 동일 본문 (검수의 source of truth)
  "tags":      Record<string, string>,
                         // 다양성 분석용 구조화 태그
                         // angle / distance / expression / lighting / outfit / scene 등
  "qa_status": "draft" | "needs_review" | "approved" | "rejected",
  "qa_by":     string | null,
  "notes":     string
}
```

- 진실의 단일 출처는 `captions.jsonl`. sidecar `.txt` 는 트레이너가
  읽기 위해 동기화된 결과물이다. 캡션을 수정할 때는 `.jsonl` 을 고치고
  스크립트로 sidecar 를 재생성하는 흐름을 권장한다 (스크립트는 별도
  PR 에서 추가).
- `tags` 는 학습 자체에는 들어가지 않는다. 다양성 체크리스트 자동 집계와
  rejected 컷 추적에 쓴다.

## placeholder 이미지

`raw/`, `curated/` 안 PNG 들은 `_generate_placeholders.py` 로 만든 단색
플랫 이미지다. 실제 학습용 이미지가 아니고 파일 형태만 보여준다.
재생성하려면 `python3 _generate_placeholders.py`.
