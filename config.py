import os

from dotenv import load_dotenv

# 로컬은 .env 값을 환경 변수로 불러온다
load_dotenv()

# 게임 설정
PROBLEM = (
    "한 남자가 며칠 동안 매일 편의점에서 삼각김밥 하나를 사고 영수증을 꼭 받아 갔다. "
    "그러던 어느 날 그는 영수증을 한참 들여다보더니 눈물을 흘렸다. 왜일까?"
)
LABELS = ["예", "아니오", "상관없음", "애매함", "질문불가"]
NOT_YES_NO = "예/아니오만 가능합니다"  # 예/아니오로 답할 수 없는 질문에 보여 줄 문구
MAX_QUESTION_LEN = 100  # 질문 글자 수 제한
MAX_ATTEMPTS = 3
MAX_QUESTIONS = 30  # 질문을 다 쓰면 정답만 제출할 수 있다
# (힌트 시크릿 이름, 몇 번째 질문 이후에 보여 줄지). 힌트 문구는 공개 레포에 두지 않는다
HINTS = [("HINT_1", 5), ("HINT_2", 10)]
MAX_ANSWER_LEN = 200
MIN_ANSWER_LEN = 10  # 이보다 짧은 정답 답안은 AI를 부르지 않고 다시 쓰게 한다
MODELS = ["openai/gpt-oss-20b"]  # 한도가 차면 Gemini 예비로 넘어간다
USE_GEMINI = False  # True로 바꾸면 Groq 한도가 찼을 때 Gemini(gemini.py)로 넘어간다. 지금은 꺼 둔다


def _secrets_file_exists() -> bool:
    paths = [
        os.path.expanduser("~/.streamlit/secrets.toml"),
        os.path.join(os.getcwd(), ".streamlit", "secrets.toml"),
    ]
    return any(os.path.exists(p) for p in paths)


def get_secret(name: str) -> str:
    # st.secrets는 set_page_config 뒤에 건드려야 해서 호출할 때 읽는다
    value = os.getenv(name, "")
    if value:
        return value
    if not _secrets_file_exists():
        return ""  # 파일이 없을 때 st.secrets를 건드리면 화면에 오류 상자가 뜬다
    try:
        import streamlit as st

        return st.secrets[name]  # 배포 환경의 Streamlit Secrets
    except Exception:
        return ""
