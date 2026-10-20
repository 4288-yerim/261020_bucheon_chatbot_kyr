from typing import List, Optional

import httpx
from groq import Groq, APIError, RateLimitError

from config import GEMINI_MODEL, LABELS, MODELS, NOT_YES_NO, get_secret
from prompts import build_judge_prompt, build_question_prompt

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 한도(429)가 찬 모델. 앱이 재시작될 때까지 건너뛴다. 서버 전체(모든 접속자)가 공유한다
EXHAUSTED = set()


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
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
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
        parts = res.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except Exception:
        return None


def call_llm(api_key: str, messages: List[dict], gemini_key: str = "") -> Optional[str]:
    client = Groq(api_key=api_key)
    for model in MODELS:
        if model in EXHAUSTED:
            continue
        try:
            res = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_completion_tokens=800,
                reasoning_effort="low",
            )
            return (res.choices[0].message.content or "").strip()
        except RateLimitError:
            EXHAUSTED.add(model)  # 한도가 찬 모델은 이후 요청에서 건너뛴다
            continue
        except APIError:
            continue  # 그 밖의 오류는 이번 요청만 다음 모델로 넘긴다
    if gemini_key:
        return call_gemini(gemini_key, messages)  # Groq가 모두 막히면 Gemini로
    return None


def ask_question(
    api_key: str, story: str, history: List[dict], question: str, gemini_key: str = ""
) -> Optional[str]:
    messages = [{"role": "system", "content": build_question_prompt(story)}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": question})
    answer = call_llm(api_key, messages, gemini_key)
    if answer is None:
        return None
    for label in LABELS:
        if answer.startswith(label):
            return NOT_YES_NO if label == "질문불가" else label
    return NOT_YES_NO  # 라벨이 아니면 예/아니오 답이 아니므로 내용이 새지 않도록 치환


def judge_answer(api_key: str, story: str, text: str, gemini_key: str = "") -> Optional[bool]:
    messages = [
        {"role": "system", "content": build_judge_prompt(story)},
        {"role": "user", "content": f"<답안>\n{text}\n</답안>"},
    ]
    verdict = call_llm(api_key, messages, gemini_key)
    if verdict is None:
        return None
    return verdict.strip().strip(".") == "정답"
