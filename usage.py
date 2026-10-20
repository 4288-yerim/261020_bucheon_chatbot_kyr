# 앱 시작 후 모델별로 쓴 토큰 누적량(모든 접속자 합계). 앱이 재시작되면 0부터 다시 센다
USED_TOKENS = {}


def log_usage(model: str, prompt_tokens: int, completion_tokens: int, headers=None):
    # 토큰 사용량과 남은 한도를 서버 로그(Manage app 로그, 로컬은 터미널)에 print로 남긴다
    try:
        total = (prompt_tokens or 0) + (completion_tokens or 0)
        USED_TOKENS[model] = USED_TOKENS.get(model, 0) + total
        line = (
            f"[토큰] {model} | 이번 호출 입력 {prompt_tokens} + 출력 {completion_tokens} = {total}"
            f" | 앱 시작 후 누적 {USED_TOKENS[model]}"
        )
        if headers is not None:
            get = headers.get
            line += (
                f" | 남은 요청 {get('x-ratelimit-remaining-requests')}/{get('x-ratelimit-limit-requests')}"
                f" | 남은 토큰 {get('x-ratelimit-remaining-tokens')}/{get('x-ratelimit-limit-tokens')}"
                f" | 초기화 요청 {get('x-ratelimit-reset-requests')}, 토큰 {get('x-ratelimit-reset-tokens')}"
            )
        print(line, flush=True)
    except Exception:
        pass  # 로그 출력이 실패해도 게임은 계속 돌아가야 한다
