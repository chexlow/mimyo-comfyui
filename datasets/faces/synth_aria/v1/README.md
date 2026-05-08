# synth_aria face dataset — v1

| field | value |
|---|---|
| Slug | `synth_aria` |
| Trigger | `m1my0_aria` |
| Subject class | synthetic (가상 인물) |
| Caption format | natural language |
| Status | scaffold + reference example only |
| License | internal_only |
| Consent | synthetic_subject |

이 데이터셋은 가상 인물 `synth_aria` 를 대상으로 하며, 데이터셋 자체의
파이프라인을 검증하기 위한 reference 다. 실제 학습용 컷은 `raw/` 와
`curated/` 에 채워야 하고, 형태 예시는 `_example/` 디렉토리를 참고한다.

## 디렉토리

```
v1/
├── manifest.json                # public 메타 (git 추적)
├── manifest.private.json        # private 메타 (git 제외) — 템플릿은 _example/ 참조
├── README.md                    # 이 문서
├── captions.jsonl               # 캡션 + 검수 상태 (git 제외) — 형식은 _example/ 참조
├── raw/                         # 원본 백업 (git 제외, S3 동기화)
├── curated/                     # 학습 입력 (git 제외, S3 동기화)
│   ├── 1024/
│   ├── 1280/
│   └── 1536/
└── _example/                    # git 추적 reference layout — 명명 규칙 / sidecar / jsonl 예시
```

## 캡션 가이드

자연어 문장으로 작성한다. booru 태그 형식 그대로 쓰지 않는다.

- **가변 속성만 캡션에**: 의상, 표정, 조명, 배경, 거리, 자세, 액션
- **인물 고유 특징(눈/입/얼굴형 등)은 캡션에서 뺀다** — trigger 가 흡수하도록
- 트리거는 문장 맨 앞:
  `m1my0_aria, a young woman in a beige knit cardigan, sitting in a cafe by the window, soft afternoon light, three-quarter view`

## 다양성 체크리스트

큐레이션 단계에서 이 표가 균형 있게 채워졌는지 본다. `captions.jsonl`
의 `tags` 필드를 집계해서 자동으로 채울 수 있다.

- [ ] 각도: 정면 / 3·4 / 측면 — 각각 ≥ 5장
- [ ] 거리: 클로즈업 / 상반신 / 전신 — 각각 ≥ 5장
- [ ] 조명: 자연광 / 실내 / 역광 / 야간
- [ ] 표정: 무표정 / 미소 / 활짝 / 진지함
- [ ] 의상: 3종 이상
- [ ] 배경: 단색 / 실내 / 실외

## 큐레이션 룰

- short side ≥ 1024 (이상적으로 1280~1536). 그 미만은 raw 에만 보관하고
  curated 에 넣지 않는다
- 워터마크 / 자막 / 로고는 가리거나 crop
- 동일 컷에서 살짝 다른 프레임 여러 장은 한 장만 선택 (perceptual hash
  중복 제거)
- 얼굴 부분이 전체 프레임의 5% 미만으로 너무 작은 컷은 제외

## 작업 순서 권장

1. **수집**: 원본을 `raw/<seq>_<session-tag>.<ext>` 로 적재
2. **큐레이션**: 합격 컷을 `curated/<bucket>/<seq>_<scene-slug>.<ext>` 로 복사
3. **캡션**: `captions.jsonl` 한 줄 추가 + 같은 본문을 sidecar `.txt` 로 저장
4. **검수**: 각 행 `qa_status` 를 `draft → needs_review → approved` 로 진행
5. **manifest 갱신**: `image_count` 와 `resolution_buckets` 동기화
6. **S3 sync**: `raw/`, `curated/`, `captions.jsonl`, `manifest.private.json` 만 push
