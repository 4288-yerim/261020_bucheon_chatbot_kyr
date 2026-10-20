import re

import streamlit as st

from config import (
    HINTS,
    MAX_ANSWER_LEN,
    MAX_ATTEMPTS,
    MAX_QUESTION_LEN,
    MAX_QUESTIONS,
    MIN_ANSWER_LEN,
    PROBLEM,
    USE_GEMINI,
    get_secret,
)
from llm import ask_question, judge_answer

st.set_page_config(
    page_title="매일 삼각김밥을 사는 남자",
    page_icon="🔎",
    menu_items={"Get help": None, "Report a bug": None},  # 오른쪽 위 메뉴에서 도움말/버그 신고를 숨긴다
)  # 첫 Streamlit 명령이어야 한다

# 1. 환경 변수 불러오기 (로컬은 .env, 배포는 Streamlit Secrets)
GROQ_API_KEY = get_secret("GROQ_API_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY") if USE_GEMINI else ""  # Gemini를 끄면 키도 읽지 않는다
CASE_STORY = get_secret("CASE_STORY")  # 정답 전문(한글). 정답 공개 화면에만 쓴다. 공개 레포에 두지 않는다
PROMPT_STORY = get_secret("CASE_STORY_EN") or CASE_STORY  # AI에게 보내는 정답(영어). 없으면 한글을 쓴다
HINT_TEXTS = [(get_secret(name), after) for name, after in HINTS]  # 힌트 문구(한글). 비어 있으면 건너뛴다


# 답 라벨별 색. 라벨이 아닌 안내 문구("예/아니오만 가능합니다")는 파란색으로 보여 준다
LABEL_COLORS = {"예": "green", "아니오": "red", "상관없음": "gray", "애매함": "orange"}


def escape_md(text: str) -> str:
    # 사용자가 입력한 글이 마크다운 서식으로 읽히지 않게 특수문자를 막는다
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|>~$:])", r"\\\1", text)


def reset_game():
    st.session_state.messages = []
    st.session_state.attempts = 0
    st.session_state.finished = False
    st.session_state.solved = False
    st.session_state.notice = ""
    st.session_state.q_error = ""


@st.dialog("🎮 게임 방법")
def show_help():
    hint_turns = ", ".join(f"{after}번째" for _, after in HINTS)
    st.markdown(
        f"""
**1. 목표**

한 줄 문제 속에 숨겨진 사연을 추리해서 맞히는 게임이에요.

**2. 질문하기**

아래 입력창에 예/아니오로 답할 수 있는 질문을 하세요. 출제자는 아래 네 가지로만 답해요.

- **예 / 아니오** : 질문 내용이 진상과 맞는지 틀린지
- **상관없음** : 진상과 관계가 없거나 정해져 있지 않은 내용
- **애매함** : 대답하기 애매한 질문

"만약 ~였다면?" 같은 가정 질문도 상관없음으로 처리돼요.

"왜?", "누구야?" 같은 열린 질문에는 "예/아니오만 가능합니다"라고 안내해요.

**3. 질문 횟수와 힌트**

질문은 최대 {MAX_QUESTIONS}번까지 할 수 있어요. 질문을 모두 써도 정답은 제출할 수 있어요.
질문이 {hint_turns}에 도달하면 왼쪽 사이드바의 힌트 버튼이 차례로 열려요. 버튼을 누르면 팝업으로 힌트를 볼 수 있어요.

**4. 정답 제출**

왼쪽 사이드바에 추리한 내용을 적어 제출하세요. 정답은 {MAX_ATTEMPTS}번까지 제출할 수 있어요.
(모바일에서는 화면 왼쪽 위의 화살표를 눌러 사이드바를 열 수 있어요.)

**5. 끝**

정답을 맞히거나 정답 제출 기회를 모두 쓰면 사연이 공개되고 게임이 끝나요.

**⚠️ 주의 사항**

- 질문 길이 제한은 {MAX_QUESTION_LEN}자입니다.
- 한 번에 하나의 질문만 해주세요.
    - 한 번에 여러 질문을 하면 AI가 애매하다고 판단해요.
"""
    )


@st.dialog("💡 힌트")
def show_hint(number: int, text: str):
    st.markdown(f"**힌트 {number}**")
    st.write(text)


@st.dialog("🔍 사연")
def show_truth():
    if st.session_state.solved:
        st.success("🎉 정답입니다! 사연은 이렇습니다.")
    else:
        st.error("정답 제출 기회를 모두 사용했어요. 사연은 이렇습니다.")
    st.write("\n\n".join(re.split(r"(?<=\.)\s+", CASE_STORY)))  # 문장마다 줄을 바꿔 보여 준다


# 2. 화면 구성
st.header("🔎 매일 삼각김밥을 사는 남자")  # st.title보다 작은 제목

# 사이드바 내용을 세로 가운데로 옮긴다
st.markdown(
    """
<style>
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 80vh;
}
/* 화면이 넓을 때는 사이드바를 접었다 펴는 버튼을 숨겨서 항상 고정해 둔다. 좁은 화면(모바일)은 기본 동작 유지 */
@media (min-width: 768px) {
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: none;
    }
}
/* 질문과 답 사이를 조금 띄워 읽기 쉽게 한다 */
[data-testid="stChatMessage"] {
    padding: 0.6rem 0.8rem;
    margin-bottom: 0.4rem;
}
/* 오른쪽 위 메뉴에서 Settings(테마)만 남긴다: 1번 Rerun, 3번 이후(Print, Record, About)를 숨긴다 */
[data-testid="stMainMenuList"] > :nth-child(1),
[data-testid="stMainMenuList"] > :nth-child(n+3) {
    display: none;
}
</style>
""",
    unsafe_allow_html=True,
)

if not GROQ_API_KEY or not CASE_STORY:
    st.error("GROQ_API_KEY 또는 CASE_STORY가 설정되지 않았어요. README를 확인해 주세요.")
    st.stop()

if "messages" not in st.session_state:
    reset_game()

st.info(PROBLEM)
st.caption("예/아니오로 답할 수 있는 질문을 자유롭게 하세요. 출제자는 예 / 아니오 / 상관없음 / 애매함으로만 답해요.")

q_count = len(st.session_state.messages) // 2
questions_left = MAX_QUESTIONS - q_count

# 3. 사이드바: 게임 방법 버튼, 정답 제출, 힌트 버튼
with st.sidebar:
    help_clicked = st.button("🎮 게임 방법", use_container_width=True)
    st.header("정답 제출")
    left = MAX_ATTEMPTS - st.session_state.attempts
    st.write(f"질문한 횟수 : {q_count} / {MAX_QUESTIONS}번")
    st.write(f"정답 제출 기회 : {left} / {MAX_ATTEMPTS}")
    with st.form("answer_form", clear_on_submit=True):
        guess = st.text_area(
            "남자가 매일 편의점에 간 이유와, 그날 영수증을 보고 운 이유를 적어 주세요.",
            max_chars=MAX_ANSWER_LEN,
            disabled=st.session_state.finished,
        )
        submitted = st.form_submit_button("정답 제출", disabled=st.session_state.finished)
    if st.session_state.notice:
        st.warning(st.session_state.notice)
    for i, (hint, after) in enumerate(HINT_TEXTS, start=1):
        if hint and st.button(
            f"💡 힌트 {i}",
            key=f"hint_{i}",
            disabled=q_count < after,
            help=f"질문을 {after}번 하면 열려요",
            use_container_width=True,
        ):
            show_hint(i, hint)
    if st.button(
        "🔍 정답 보기",
        disabled=not st.session_state.finished,
        help="정답을 맞히거나 정답 제출 기회를 모두 쓰면 열려요",
        use_container_width=True,
    ):
        show_truth()

if help_clicked:
    show_help()
elif not st.session_state.get("help_seen"):
    st.session_state.help_seen = True  # 처음 접속했을 때 한 번만 자동으로 띄운다
    show_help()

if submitted and guess.strip():
    if len(guess.strip()) < MIN_ANSWER_LEN:
        # 너무 짧은 답안은 AI를 부르지 않고 기회도 차감하지 않는다
        st.session_state.notice = f"답안이 너무 짧아요. {MIN_ANSWER_LEN}자 이상 적어 주세요. (기회는 차감되지 않아요)"
        st.rerun()
    with st.spinner("판정 중..."):
        result = judge_answer(GROQ_API_KEY, PROMPT_STORY, guess.strip(), GEMINI_API_KEY)
    if result is None:
        st.session_state.notice = "AI 오류 발생. 정답을 다시 제출해주세요. (기회는 차감되지 않아요)"
    else:
        st.session_state.attempts += 1
        left = MAX_ATTEMPTS - st.session_state.attempts
        if result:
            st.session_state.solved = True
            st.session_state.finished = True
            st.session_state.notice = ""
        elif left <= 0:
            st.session_state.finished = True
            st.session_state.notice = ""
        else:
            st.session_state.notice = (
                "오답이에요. 정답에는 '남자가 매일 편의점에 간 이유'와 "
                f"'그날 영수증을 보고 운 이유'를 모두 적어야 해요. (정답 제출 기회 {left} / {MAX_ATTEMPTS})"
            )
    st.rerun()

# 4. 질문 입력
if questions_left <= 0 and not st.session_state.finished:
    st.info("질문을 모두 사용했어요. 이제 정답만 제출할 수 있어요.")
question = st.chat_input(
    "출제자에게 질문하세요",
    max_chars=MAX_QUESTION_LEN,
    disabled=st.session_state.finished or questions_left <= 0,
)
if question and len(question) > MAX_QUESTION_LEN:
    st.session_state.q_error = f"질문은 {MAX_QUESTION_LEN}자까지 입력할 수 있어요."
    st.rerun()
if question and questions_left > 0:
    with st.spinner("출제자가 생각 중..."):
        label = ask_question(GROQ_API_KEY, PROMPT_STORY, st.session_state.messages, question, GEMINI_API_KEY)
    if label is None:
        # 실패한 질문은 대화 기록에 넣지 않아서 질문 횟수가 차감되지 않는다
        st.session_state.q_error = "AI 오류 발생. 질문을 다시 입력해주세요."
    else:
        st.session_state.messages.append({"role": "user", "content": question})
        st.session_state.messages.append({"role": "assistant", "content": label})
        st.session_state.q_error = ""
        st.session_state.notice = ""
    st.rerun()

# 5. 대화 기록 출력 (system 메시지는 담지 않으므로 보이지 않는다)
question_no = 0
for m in st.session_state.messages:
    if m["role"] == "user":
        question_no += 1
        with st.chat_message("user", avatar="🙋"):
            st.markdown(f"**Q{question_no}.** {escape_md(m['content'])}")
    else:
        with st.chat_message("assistant", avatar="🕵️"):
            color = LABEL_COLORS.get(m["content"], "blue")
            if m["content"] in LABEL_COLORS:
                st.markdown(f"### :{color}[{m['content']}]")  # 라벨은 크고 진하게
            else:
                st.markdown(f":{color}[**{m['content']}**]")
if st.session_state.q_error:
    st.error(st.session_state.q_error)

# 6. 종료 안내. 사연은 사이드바의 '정답 보기' 버튼으로 볼 수 있다
if st.session_state.finished:
    if st.session_state.solved:
        st.success("🎉 정답입니다! 왼쪽 사이드바의 '정답 보기'를 눌러 사연을 확인하세요.")
    else:
        st.error("정답 제출 기회를 모두 사용했어요. 왼쪽 사이드바의 '정답 보기'를 눌러 사연을 확인하세요.")
