import re
from typing import List, Optional

from groq import Groq, APIError, RateLimitError

from config import LABELS, MODELS, NOT_YES_NO, USE_GEMINI
from gemini import call_gemini
from prompts import build_judge_prompt, build_question_prompt
from usage import log_usage

# 한도(429)가 찬 모델. 앱이 재시작될 때까지 건너뛴다. 서버 전체(모든 접속자)가 공유한다
EXHAUSTED = set()


def call_llm(api_key: str, messages: List[dict], gemini_key: str = "") -> Optional[str]:
    client = Groq(api_key=api_key)
    for model in MODELS:
        if model in EXHAUSTED:
            continue
        try:
            raw = client.chat.completions.with_raw_response.create(
                model=model,
                messages=messages,
                temperature=0,
                max_completion_tokens=800,
                reasoning_effort="low",
            )
            res = raw.parse()
            log_usage(model, res.usage.prompt_tokens, res.usage.completion_tokens, raw.headers)
            return (res.choices[0].message.content or "").strip()
        except RateLimitError:
            EXHAUSTED.add(model)  # 한도가 찬 모델은 이후 요청에서 건너뛴다
            continue
        except APIError:
            continue  # 그 밖의 오류는 이번 요청만 다음 모델로 넘긴다
    if USE_GEMINI and gemini_key:
        return call_gemini(gemini_key, messages)  # Groq가 모두 막히면 Gemini로 (USE_GEMINI가 True일 때만)
    return None


# 정답이나 지시문을 직접 요구하는 요청. 이런 질문은 AI를 부르지 않고 바로 질문불가로 처리한다
META_REQUEST = re.compile(
    r"프롬프트|지시\s*문|시스템\s*(프롬|메시지|지시)|system|instruction|ignore"
    r"|이전\s*(지시|명령)|정답\s*(이|을|좀)?\s*(뭐|뭔|알려|말해|가르쳐|공개|보여|출력)",
    re.IGNORECASE,
)


def ask_question(
    api_key: str, story: str, history: List[dict], question: str, gemini_key: str = ""
) -> Optional[str]:
    if META_REQUEST.search(question):
        return NOT_YES_NO
    messages = [{"role": "system", "content": build_question_prompt(story)}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": question})
    answer = call_llm(api_key, messages, gemini_key)
    if answer is None:
        return None
    # 라벨 바로 뒤에 다른 한글이 붙으면("예를 들어…") 라벨로 보지 않는다
    match = re.match("(" + "|".join(LABELS) + ")(?![가-힣])", answer)
    if match is None:
        return None  # 빈 응답이거나 라벨이 아니면 AI 오류로 보고 다시 입력하게 한다
    label = match.group(1)
    return NOT_YES_NO if label == "질문불가" else label


def judge_answer(api_key: str, story: str, text: str, gemini_key: str = "") -> Optional[bool]:
    messages = [
        {"role": "system", "content": build_judge_prompt(story)},
        {"role": "user", "content": f"<답안>\n{text}\n</답안>"},
    ]
    verdict = call_llm(api_key, messages, gemini_key)
    if not verdict:
        return None  # 빈 응답은 오답이 아니라 AI 오류로 보고 기회를 차감하지 않는다
    return verdict.strip().strip(".") == "정답"
