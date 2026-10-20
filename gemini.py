# Gemini 예비 호출. config.py의 USE_GEMINI가 True일 때만 llm.py가 이 파일을 쓴다
from typing import List, Optional

import httpx

from config import get_secret
from usage import log_usage

GEMINI_MODEL = "gemini-3.8-flash"  # GEMINI_MODEL 시크릿(.env)이 있으면 그 값을 쓴다
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def call_gemini(api_key: str, messages: List[dict]) -> Optional[str]:
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
        if m["role"] != "system"
    ]
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0, "maxOutputTokens": 1024},
    }
    model = get_secret("GEMINI_MODEL") or GEMINI_MODEL
    try:
        res = httpx.post(
            GEMINI_URL.format(model=model),
            headers={"x-goog-api-key": api_key},
            json=body,
            timeout=60,
        )
        res.raise_for_status()
        data = res.json()
        usage = data.get("usageMetadata", {})
        log_usage(model, usage.get("promptTokenCount"), usage.get("candidatesTokenCount"))
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except Exception:
        return None
