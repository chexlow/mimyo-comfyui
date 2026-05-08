"""5단계 — 캡션 + sidecar + captions.jsonl.

Provider 두 가지:
  - ollama   : qwen3-vl:4b (system prompt 로 spec 룰 강제)
  - florence : thwri/CogFlorence-2-Large-Freeze (task-token 캡션 → 후처리로 spec 강제)

공통 후처리 (`_post_process`):
  - trigger 첫머리 prepend
  - 식별 속성(eye color/lip shape 등) regex 검출 → flag
  - 길이 검사
"""
from __future__ import annotations
import base64
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from tqdm import tqdm

from .paths import DatasetPaths, BUCKETS
from .report import update_stage


# ─────────────────────────────────────────────────────────────────────────────
# 공통: 후처리 + sidecar 헬퍼
# ─────────────────────────────────────────────────────────────────────────────

FORBIDDEN_PATTERNS = [
    # 눈
    r"\beye color\b", r"\b(dark|light|black|brown|blue|green|hazel)\s+eyes?\b",
    # 얼굴 구조
    r"\bcheekbones?\b", r"\bjawline\b", r"\bnose shape\b", r"\blip shape\b",
    r"\b(round|oval|square|heart-shaped)\s+face\b",
    # 헤어 — color / length / style 모두 식별 속성
    r"\b(long|short|medium|shoulder-length)\s+(black|brown|blonde|blond|red|grey|gray|white|dark|light)?\s*hair\b",
    r"\b(black|brown|blonde|blond|red|grey|gray|white|dark|light)\s+hair\b",
    r"\bwith\s+(?:[a-z\s]+\s+)?hair\b",
    # 워터마크 / 자막
    r"\bwatermark\b", r"\b(text|caption|subtitle|logo)\s+(in|at|on|overlay)\b",
]
FORBIDDEN_RE = re.compile("|".join(FORBIDDEN_PATTERNS), re.IGNORECASE)

# review 필요한 warning 등급 flag (info 등급은 review 안 만듦)
WARNING_FLAGS = {
    "identity_attribute_detected",
    "length_capped",
    "too_long",
    "too_short",
}

# hair 묘사 패턴 — 길이? + 색? + "hair" + 부속 (bangs/highlights 등) 옵셔널
_HAIR_DESC = (
    r"(?:long|short|medium|shoulder-length|straight|wavy|curly|tied)?\s*"
    r"(?:black|brown|blonde|blond|red|grey|gray|white|dark|light|auburn|pink|"
    r"vibrant|silver|orange|natural)?\s*"
    r"hair"
    r"(?:\s+and\s+(?:bangs|highlights|pink\s+highlights|side\s+bangs))?"
)


def _strip_hair_phrases(text: str) -> tuple[str, bool]:
    """caption 에서 hair 식별 속성 자동 제거. 잔여물 정리. (new_text, changed)"""
    original = text

    # "(a) woman/girl with [hair] (and )?(wearing|in|standing|sitting|...)"
    #   → "(a) woman/girl \\next"
    text = re.sub(
        r"\b((?:a|an|the)\s+)?(woman|girl|person|lady|female)\s+with\s+"
        + _HAIR_DESC
        + r"\s+(?:and\s+)?(wearing|in\s+a|in\s+an|standing|sitting|holding|"
        r"smiling|laughing|posing|set\s+against|adorned\s+with)",
        r"\1\2 \3",
        text,
        flags=re.IGNORECASE,
    )

    # 잔여: "with [hair] and X" → "with X" (다른 묘사로 이어짐)
    text = re.sub(
        r"\bwith\s+" + _HAIR_DESC + r"\s+and\s+",
        "with ",
        text,
        flags=re.IGNORECASE,
    )
    # ", with [hair]," / ". with [hair]." 끝
    text = re.sub(
        r"[,.]?\s*with\s+" + _HAIR_DESC + r"\s*([,.])",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )
    # 중간에 그냥 ", [hair description]" 으로 들어간 케이스
    text = re.sub(
        r",\s*" + _HAIR_DESC + r"\s*(?=,|\.|$)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # "her hair pulled back / styled / tied" 같은 헤어스타일 묘사 phrase
    text = re.sub(
        r",?\s*(?:her|the)\s+hair\s+"
        r"(?:pulled|styled|tied|swept|cascading|flowing|in\s+a)\s+[^,.]+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # 정리: 중복 공백/콤마/문장 시작 콤마
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*,+\s*", ", ", text)
    text = re.sub(r"^\s*,\s*", "", text).strip()

    return text, text != original

# Florence / CogFlorence 가 자주 시작하는 boilerplate. 의미 없는 prefix 라 strip.
BOILERPLATE_RE = re.compile(
    r"^("
    r"the\s+image\s+(shows|depicts|features|displays|presents|captures|portrays)\s+"
    r"|this\s+image\s+(shows|depicts|is|features)\s+"
    r"|this\s+is\s+(a|an)\s+(photograph|photo|picture|image|portrait)\s+(of\s+)?"
    r"|in\s+this\s+(image|photo|picture),?\s+"
    r"|a\s+(photograph|photo|picture|portrait)\s+(of|shows|depicts)\s+"
    r"|an?\s+image\s+(of|shows|depicting)\s+"
    r")",
    re.IGNORECASE,
)

MAX_WORDS = 100  # florence 가 매우 길게 줄 수 있어 hard cap


def _post_process(
    caption: str,
    trigger: str,
    *,
    hard_cap: bool = True,
    strip_hair: bool = True,
) -> tuple[str, list[str]]:
    flags: list[str] = []
    text = caption.strip()
    text = text.strip("`'\"")
    text = re.sub(r"^(caption[:\-\s]+)", "", text, flags=re.IGNORECASE)

    # Florence boilerplate strip — trigger prepend 전에 정리
    stripped = BOILERPLATE_RE.sub("", text)
    if stripped != text:
        flags.append("boilerplate_stripped")
        text = stripped

    # hair 식별 속성 자동 제거
    if strip_hair:
        new_text, changed = _strip_hair_phrases(text)
        if changed:
            text = new_text
            flags.append("hair_stripped")

    if not text.lower().startswith(trigger.lower()):
        text = f"{trigger}, {text}"
        flags.append("trigger_prepended")

    if FORBIDDEN_RE.search(text):
        flags.append("identity_attribute_detected")

    word_count = len(text.split())
    if hard_cap and word_count > MAX_WORDS:
        words = text.split()
        text = " ".join(words[:MAX_WORDS])
        # 마지막 . 뒤 잘리면 . 보충
        if not text.endswith((".", "?", "!")):
            text = text.rstrip(",;:") + "."
        flags.append("length_capped")
        word_count = MAX_WORDS

    if word_count < 20:
        flags.append("too_short")
    elif word_count > 120:
        flags.append("too_long")

    return text, flags


_SLUG_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "into",
    "and", "or", "but", "as", "this", "that", "these", "those",
    "image", "photo", "photograph", "picture", "portrait", "shows",
    "depicts", "features", "displays", "captures", "showing",
}


def _scene_slug(text: str) -> str:
    """캡션에서 의미 있는 짧은 scene slug 추출."""
    # trigger token 다음 첫 chunk 사용 (콤마/마침표 기준)
    parts = re.split(r"[,.]", text, maxsplit=3)
    # parts[0] 은 trigger, parts[1+] 가 묘사
    chunk = " ".join(p.strip() for p in parts[1:3]) if len(parts) >= 2 else text
    words = re.findall(r"[a-zA-Z]+", chunk.lower())
    meaningful = [w for w in words if w not in _SLUG_STOPWORDS and len(w) > 1]
    slug = "-".join(meaningful[:3]) or "scene"
    return slug[:40]


def _rename_with_slug(path: Path, scene_slug: str) -> Path:
    """이미지를 새 slug 으로 rename + 같은 seq 의 옛 .txt sidecar 모두 정리."""
    m = re.match(r"^(\d{4})_(.+)\.([^.]+)$", path.name)
    if not m:
        return path
    seq, _, ext = m.groups()
    new_name = f"{seq}_{scene_slug}.{ext}"
    new_path = path.with_name(new_name)

    # 같은 seq 의 옛 .txt sidecar 들 정리 (orphan 방지)
    for stale_txt in path.parent.glob(f"{seq}_*.txt"):
        # 새 sidecar 자체는 아직 없음 (이 함수 다음에 작성됨)
        try:
            stale_txt.unlink()
        except OSError:
            pass

    if new_path != path:
        path.rename(new_path)
    return new_path


def _all_curated(paths: DatasetPaths) -> list[Path]:
    files: list[Path] = []
    for b in BUCKETS:
        d = paths.bucket_dir(b)
        if d.exists():
            files.extend(sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}))
    return files


def _is_already_captioned(f: Path) -> bool:
    sidecar = f.with_suffix(".txt")
    if not sidecar.exists() or sidecar.stat().st_size == 0:
        return False
    return sidecar.stat().st_mtime >= f.stat().st_mtime


def _read_existing_row(f: Path, base: Path) -> dict | None:
    sidecar = f.with_suffix(".txt")
    if not sidecar.exists():
        return None
    cap = sidecar.read_text().strip()
    if not cap:
        return None
    return {
        "file": str(f.relative_to(base)),
        "caption": cap,
        "qa_status": "draft",
        "qa_by": None,
        "flags": [],
        "notes": "from-cache",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Provider 1: Ollama qwen3-vl:4b
# ─────────────────────────────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_OLLAMA_MODEL = "qwen3-vl:4b"


def _ollama_system_prompt(trigger: str) -> str:
    return (
        "You are a captioner for a face LoRA training dataset.\n"
        "Output a single natural-language sentence describing the image.\n\n"
        "Rules:\n"
        f"1. Start the sentence with the trigger token: {trigger}\n"
        "2. Describe ONLY variable attributes: clothing, expression, lighting, "
        "background, framing distance (close-up / head-and-shoulders / upper body / "
        "full body), pose, action.\n"
        "3. Do NOT describe permanent identity features (eye color, lip shape, "
        "facial structure, hair color/style).\n"
        "4. Use natural-language sentences, NOT booru tags.\n"
        "5. Length: 30-80 words, single sentence.\n"
        "6. Output the caption only. No markdown, no quotes, no preamble."
    )


def _ollama_caption(image_path: Path, system: str, model: str, timeout: int = 180) -> str:
    img_b64 = base64.b64encode(image_path.read_bytes()).decode()
    payload = {
        "model": model,
        "system": system,
        "prompt": "Caption this image.",
        "images": [img_b64],
        "stream": False,
        "options": {"temperature": 0.2},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Provider 2: thwri/CogFlorence-2-Large-Freeze
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_FLORENCE_MODEL = "thwri/CogFlorence-2-Large-Freeze"
FLORENCE_TASK = "<DETAILED_CAPTION>"  # MORE_DETAILED 는 너무 길어 후처리 부담

_florence_state: dict = {"model": None, "processor": None, "device": None, "dtype": None, "id": None}


def _florence_init(model_id: str) -> None:
    if _florence_state["model"] is not None and _florence_state["id"] == model_id:
        return
    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor

    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    dtype = torch.float16 if device != "cpu" else torch.float32

    print(f"[florence] loading {model_id} on {device} ({dtype})…", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, trust_remote_code=True, torch_dtype=dtype,
    ).to(device).eval()
    processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)

    _florence_state.update(model=model, processor=processor, device=device, dtype=dtype, id=model_id)


def _florence_caption(image_path: Path) -> str:
    import torch
    from PIL import Image

    proc = _florence_state["processor"]
    model = _florence_state["model"]
    device = _florence_state["device"]
    dtype = _florence_state["dtype"]

    with Image.open(image_path) as im:
        if im.mode != "RGB":
            im = im.convert("RGB")
        inputs = proc(text=FLORENCE_TASK, images=im, return_tensors="pt").to(device, dtype)
        with torch.no_grad():
            ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=512,
                num_beams=3,
                do_sample=False,
            )
        text = proc.batch_decode(ids, skip_special_tokens=False)[0]
        parsed = proc.post_process_generation(text, task=FLORENCE_TASK, image_size=im.size)
        return parsed[FLORENCE_TASK].strip()


# ─────────────────────────────────────────────────────────────────────────────
# 공통 처리
# ─────────────────────────────────────────────────────────────────────────────

def _process_one(
    f: Path, base: Path, *, provider: str, trigger: str,
    ollama_model: str, ollama_system: str, strip_hair: bool = True,
) -> dict:
    try:
        if provider == "ollama":
            raw = _ollama_caption(f, ollama_system, ollama_model)
        elif provider == "florence":
            raw = _florence_caption(f)
        else:
            raise ValueError(f"unknown provider: {provider}")
    except Exception as e:  # noqa: BLE001
        return {"file": str(f.relative_to(base)), "caption": None, "qa_status": "error", "error": str(e)}

    caption, flags = _post_process(raw, trigger, strip_hair=strip_hair)
    slug = _scene_slug(caption)
    new_path = _rename_with_slug(f, slug)
    new_path.with_suffix(".txt").write_text(caption + "\n")

    needs_review = any(fl in WARNING_FLAGS or fl.startswith("extreme") for fl in flags)
    return {
        "file": str(new_path.relative_to(base)),
        "caption": caption,
        "qa_status": "needs_review" if needs_review else "draft",
        "qa_by": None,
        "flags": flags,
        "notes": "",
    }


def run(
    paths: DatasetPaths,
    *,
    trigger: str,
    provider: str = "ollama",
    model: str | None = None,
    parallel: int = 4,
    force: bool = False,
    strip_hair: bool = True,
) -> dict:
    files = _all_curated(paths)

    # Provider 별 init
    if provider == "ollama":
        ollama_model = model or DEFAULT_OLLAMA_MODEL
        ollama_system = _ollama_system_prompt(trigger)
        florence_model = ""
    elif provider == "florence":
        florence_model = model or DEFAULT_FLORENCE_MODEL
        _florence_init(florence_model)
        ollama_model = ""
        ollama_system = ""
    else:
        raise ValueError(f"unknown provider: {provider!r}, expected ollama|florence")

    # 캐시 분리
    pending: list[Path] = []
    cached_rows: list[dict] = []
    if force:
        pending = list(files)
    else:
        for f in files:
            if _is_already_captioned(f):
                row = _read_existing_row(f, paths.base)
                if row:
                    cached_rows.append(row)
                    continue
            pending.append(f)

    rows: list[dict] = list(cached_rows)
    t_start = time.time()

    if pending:
        # florence 는 GPU 단일 모델이라 thread 동시 호출 의미 적음. 직렬.
        # ollama 는 데몬 측 NUM_PARALLEL 만큼 동시 호출 효과.
        effective_parallel = parallel if provider == "ollama" else 1

        def _call(f: Path) -> dict:
            return _process_one(
                f, paths.base,
                provider=provider, trigger=trigger,
                ollama_model=ollama_model, ollama_system=ollama_system,
                strip_hair=strip_hair,
            )

        if effective_parallel > 1:
            with ThreadPoolExecutor(max_workers=effective_parallel) as ex:
                futures = {ex.submit(_call, f): f for f in pending}
                for fut in tqdm(as_completed(futures), total=len(futures), desc=f"caption[{provider}]", unit="img"):
                    rows.append(fut.result())
        else:
            for f in tqdm(pending, desc=f"caption[{provider}]", unit="img"):
                rows.append(_call(f))

    rows.sort(key=lambda r: r["file"])
    with paths.captions_jsonl.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    elapsed = time.time() - t_start
    payload = {
        "provider": provider,
        "model": ollama_model or florence_model,
        "parallel": parallel if provider == "ollama" else 1,
        "captioned": sum(1 for r in rows if r.get("caption") and r.get("notes") != "from-cache"),
        "from_cache": sum(1 for r in rows if r.get("notes") == "from-cache"),
        "errors": sum(1 for r in rows if r.get("qa_status") == "error"),
        "needs_review": sum(1 for r in rows if r.get("qa_status") == "needs_review"),
        "elapsed_sec": round(elapsed, 1),
    }
    update_stage(paths.report, paths.slug, paths.version, "caption", payload)
    print(f"[caption/{provider}] new={payload['captioned']}  cache={payload['from_cache']}  needs_review={payload['needs_review']}  errors={payload['errors']}  elapsed={elapsed:.1f}s")
    return payload
