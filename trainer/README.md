# trainer

Z-Image / Qwen-Image 계열 LoKr / LoRA 학습 워커. RunPod GPU pod 에서 한 번
실행되고, 데이터셋과 베이스 모델을 S3 에서 끌어와 학습한 뒤 산출물을 다시
S3 에 푸시하고 종료한다.

> 이 디렉토리는 학습 영역이다. 데이터셋(`datasets/`) 과 inference worker
> (`Dockerfile.real`, `Dockerfile.anime`) 영역과 명확히 분리된다. inference
> Dockerfile 들의 `COPY` 가 명시적이라 `trainer/` 가 자동으로 inference
> 이미지에 들어가지 않는다.

## 흐름 한 장 요약

```
[Local]                          [RunPod GPU Pod]                 [S3 (eu-ro-1, tu8qpqw6ag)]
                                                                  ├── datasets/<slug>/<v>/
bun scripts/launch.ts            entrypoint.sh
  --slug synth_aria  ──────────▶   1. validate env
  --version v1                     2. sync dataset       ◀──────── ├── bases/zimage-base/
  --config smoke                   3. sync base/turbo                   bases/zimage-turbo/
  --gpu RTX_PRO_4500               4. ai-toolkit run                    bases/adapters/...
                                   5. snapshot env/config
                                   6. push output       ─────────▶ └── trainings/<slug>/<v>/<run_id>/
                                   7. exit (pod terminates)              ├── weights/
                                                                          ├── samples/
                                                                          ├── config.snapshot.yaml
                                                                          ├── env.snapshot.json
                                                                          └── training.log
```

## 디렉토리

```
trainer/
├── README.md
├── Dockerfile.train             # CUDA 12.8 + PyTorch 2.6 + ai-toolkit
├── entrypoint.sh                # pod 에서 실행되는 워커 본체
├── configs/
│   ├── zimage-face-lokr-smoke.yaml    # 50 step 호환성 검증
│   ├── zimage-face-lokr.yaml          # 본 sweep (LoKr factor 8 / dim 32)
│   └── zimage-face-lora-fallback.yaml # LoKr 호환 실패 시 LoRA 표준 경로
├── scripts/
│   ├── launch.ts                # RunPod GraphQL API 로 pod 생성 + env 주입
│   ├── promote.ts               # trainings/<run_id>/ → loras/ 명시적 promote
│   ├── list-runs.ts             # trainings/ 인벤토리
│   └── mirror-base.sh           # HF → S3 베이스 모델 한 번 mirror (로컬 1회 실행)
└── runs/                        # (gitignore) 로컬 dryrun / 디버그 산출물
```

## 학습 프로토콜 (face LoKr)

검색 결과상 Z-Image / Qwen-Image 계열의 LoKr 호환성이 "Flux 만큼 명확하지
않음" 이라 호환성 검증을 우선한다.

1. **Smoke** (config: `zimage-face-lokr-smoke`) — 50 step, image 2~3장
   - OOM 없이 도는지 (PRO 4500 32GB 마진 확인)
   - 산출 `.safetensors` 가 ComfyUI / diffusers 에서 Z-Image-Turbo 에 정상 로드되는지
   - 첫 sample 생성 정상인지
2. **본 sweep** (config: `zimage-face-lokr`) — 2500 step, save every 250
   - factor 8, dim 32, full_rank true
   - base 학습 → turbo 추론 검증
3. **Fallback** (config: `zimage-face-lora-fallback`) — smoke 실패 시
   - LoRA rank 16, base 학습 (호환 보장)

`base 학습 → turbo 추론` 패턴을 유지한다. Turbo 직접 학습은 distillation
손상 risk 가 커서 이 워커에선 기본 경로로 두지 않는다.

## S3 prefix 컨벤션

```
s3://tu8qpqw6ag/
├── datasets/<slug>/<v>/                              # 입력 (datasets/ 영역에서 sync)
├── bases/
│   ├── zimage-base/<rev>/                            # 학습 입력
│   ├── zimage-turbo/<rev>/                           # 추론 검증용
│   └── adapters/ostris-zimage-turbo-training-adapter-v2/
└── trainings/<slug>/<v>/<run_id>/                    # 학습 산출물
    ├── weights/{final,step_*}.safetensors
    ├── samples/
    ├── config.snapshot.yaml
    ├── env.snapshot.json
    └── training.log
```

`run_id` 컨벤션: `<dataset_v>__<config-slug>__<UTC-timestamp>__<git-sha7>`
예: `v1__lokr-f8-d32-smoke__20260505T1530Z__a1b2c3d`

production 진입은 `loras/` 에 별도 promote (scripts/promote.ts).

## 환경변수 (entrypoint 가 기대하는 것)

| name | 예시 | 필수 |
|---|---|---|
| `DATASET_SLUG` | `synth_aria` | ✓ |
| `DATASET_VERSION` | `v1` | ✓ |
| `CONFIG_NAME` | `zimage-face-lokr-smoke` | ✓ |
| `BASE_MODEL` | `zimage-base` | ✓ |
| `RUN_ID` | `v1__lokr-f8-d32-smoke__20260505T1530Z__a1b2c3d` | ✓ |
| `TRIGGER_TOKEN` | `m1my0_aria` | ✓ |
| `S3_ENDPOINT` | `https://s3api-eu-ro-1.runpod.io` | ✓ |
| `S3_BUCKET` | `tu8qpqw6ag` | ✓ |
| `AWS_ACCESS_KEY_ID` | … | ✓ |
| `AWS_SECRET_ACCESS_KEY` | … | ✓ |
| `AWS_REGION` | `eu-ro-1` | ✓ |
| `HF_TOKEN` | `hf_…` | optional (HF 직접 fallback 용) |

## 베이스 모델 mirror (1회)

처음 한 번만 로컬에서 실행해 S3 에 베이스를 박아둔다.

```bash
bun ./scripts/mirror-base.sh zimage-base
bun ./scripts/mirror-base.sh zimage-turbo
bun ./scripts/mirror-base.sh adapter-v2
```

## 학습 실행 (자동)

```bash
bun trainer/scripts/launch.ts \
  --slug synth_aria \
  --version v1 \
  --config zimage-face-lokr-smoke \
  --base zimage-base \
  --trigger m1my0_aria \
  --gpu "RTX PRO 4500"
```

스크립트가 `RUN_ID` 자동 생성, RunPod GraphQL `podFindAndDeployOnDemand`
호출, env 주입, pod 생성 후 ID 반환. pod 안에서 entrypoint 실행되고 끝나면
self-terminate.

## promote (수동)

```bash
bun trainer/scripts/promote.ts <run_id> --weight final --tag synth_aria-v1
```

`trainings/<slug>/<v>/<run_id>/weights/final.safetensors` 를
`loras/<tag>.safetensors` 로 복사.

## 시크릿 처리

AWS / RunPod / HF 토큰 모두 RunPod env 에 영구 저장하지 않는다. 매번
launch 스크립트가 로컬 `~/.aws/credentials` (profile `runpod`) 와
`$RUNPOD_API_KEY` 를 읽어 pod 생성 시점에만 env 로 주입한다.
