"""
Gemini Telegram AI Agent
- 텔레그램 메시지를 받아 Gemini에게 전달
- Gemini Function Calling으로 GWS 도구 실행
- 결과를 텔레그램으로 반환
"""

import os
import json
import logging
from pathlib import Path

import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai.types import content_types
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

from tools import TOOL_DECLARATIONS, execute_tool

# ─── 로깅 설정 ───────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── 설정 로드 (dotenv) ───────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

with open(BASE_DIR / "system_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# ─── bkit 컨텍스트 로드 ──────────────────────────────────────
BKIT_PATH = os.getenv("BKIT_PATH")
if BKIT_PATH:
    bkit_gemini_md = Path(BKIT_PATH) / "GEMINI.md"
    if bkit_gemini_md.exists():
        logger.info("📚 Loading bkit context from %s", bkit_gemini_md)
        bkit_context = bkit_gemini_md.read_text(encoding="utf-8")
        SYSTEM_PROMPT += "\n\n" + "="*40 + "\n"
        SYSTEM_PROMPT += "## bkit Core Instructions\n"
        SYSTEM_PROMPT += bkit_context
        SYSTEM_PROMPT += "\n" + "="*40 + "\n"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_CHAT_ID = os.getenv("CHAT_ID")


# ─── Gemini 초기화 ──────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)

# Function Calling 도구를 genai.protos.Tool로 변환
tools_proto = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    k: genai.protos.Schema(
                        type=(
                            genai.protos.Type.STRING
                            if v.get("type") == "string"
                            else genai.protos.Type.INTEGER
                            if v.get("type") == "integer"
                            else genai.protos.Type.BOOLEAN
                            if v.get("type") == "boolean"
                            else genai.protos.Type.STRING
                        ),
                        description=v.get("description", ""),
                    )
                    for k, v in t.get("parameters", {}).get("properties", {}).items()
                },
                required=t.get("parameters", {}).get("required", []),
            ),
        )
        for t in TOOL_DECLARATIONS
    ]
)

model = genai.GenerativeModel(
    "gemini-3-flash-preview",
    system_instruction=SYSTEM_PROMPT,
    tools=[tools_proto],
)

# ─── 대화 세션 관리 ─────────────────────────────────────────
chat_sessions: dict = {}

MAX_TELEGRAM_MSG_LEN = 4096
MAX_TOOL_ITERATIONS = 15  # 도구 호출 무한 루프 방지 (bkit 연동으로 인한 증가)


# ─── 보안 필터 ───────────────────────────────────────────────
def is_authorized(update: Update) -> bool:
    if ALLOWED_CHAT_ID in (None, "", "YOUR_CHAT_ID"):
        return True
    return str(update.effective_chat.id) == str(ALLOWED_CHAT_ID)


# ─── 도구 호출 처리 루프 ────────────────────────────────────
async def process_with_tools(chat, user_text: str) -> str:
    """
    Gemini에게 메시지를 보내고, Function Calling이 있으면
    도구를 실행한 뒤 결과를 다시 전달하는 루프를 반복합니다.
    """
    response = chat.send_message(user_text)

    for iteration in range(MAX_TOOL_ITERATIONS):
        # Function Call이 있는지 확인
        candidate = response.candidates[0]
        parts = candidate.content.parts

        function_calls = [p for p in parts if p.function_call.name]

        if not function_calls:
            # 도구 호출 없음 → 텍스트 응답 반환
            text_parts = [p.text for p in parts if p.text]
            return "\n".join(text_parts) if text_parts else "⚠️ 응답을 생성할 수 없습니다."

        # 도구 실행 및 결과 수집
        function_responses = []
        for fc in function_calls:
            tool_name = fc.function_call.name
            tool_args = dict(fc.function_call.args) if fc.function_call.args else {}

            logger.info("🔧 Tool call: %s(%s)", tool_name, tool_args)

            # 도구 실행
            result = execute_tool(tool_name, tool_args)
            logger.info("📋 Tool result: %s", result[:200])

            function_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tool_name,
                        response={"result": result},
                    )
                )
            )

        # 도구 결과를 Gemini에게 전달
        response = chat.send_message(
            genai.protos.Content(parts=function_responses)
        )

    return "⚠️ 도구 호출이 최대 횟수를 초과했습니다."


# ─── /start 명령어 ───────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    welcome = (
        "🤖 **Gemini AI Agent**가 활성화되었습니다!\n\n"
        f"📌 Chat ID: `{chat_id}`\n\n"
        "**사용 가능한 기능:**\n"
        "📧 이메일: '읽지 않은 메일 보여줘'\n"
        "📅 캘린더: '오늘 일정 알려줘'\n"
        "📁 드라이브: '최근 파일 목록'\n"
        "💻 시스템: 'gcloud 프로젝트 목록'\n"
        "💬 일반 대화: 아무 질문이나!\n\n"
        "**명령어:**\n"
        "/start - 도움말\n"
        "/reset - 대화 초기화\n"
        "/status - 시스템 상태"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


# ─── /reset 명령어 ───────────────────────────────────────────
async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]
    await update.message.reply_text("🔄 대화 히스토리가 초기화되었습니다.")


# ─── /status 명령어 ──────────────────────────────────────────
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    import shutil

    gwcli_path = shutil.which("gwcli")
    gcloud_path = shutil.which("gcloud")

    status_msg = (
        "📊 **시스템 상태**\n\n"
        f"🤖 Gemini: `gemini-3-flash-preview` ✅\n"
        f"📡 Telegram Bot: 활성 ✅\n"
        f"🔧 gwcli: {'`' + gwcli_path + '` ✅' if gwcli_path else '미설치 ❌'}\n"
        f"☁️ gcloud: {'`' + gcloud_path + '` ✅' if gcloud_path else '미설치 ❌'}\n"
        f"🧠 활성 세션: {len(chat_sessions)}개"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")


# ─── 메시지 처리 ─────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        logger.warning("Unauthorized: %s", update.effective_chat.id)
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id
    logger.info("📩 Message from %s: %s", chat_id, user_text[:80])

    # "처리 중" 표시
    processing_msg = await update.message.reply_text("⏳ 처리 중...")

    try:
        # 채팅 세션 가져오기 또는 생성
        if chat_id not in chat_sessions:
            chat_sessions[chat_id] = model.start_chat(
                history=[],
                enable_automatic_function_calling=False,
            )

        chat = chat_sessions[chat_id]

        # Gemini에게 처리 위임 (도구 호출 포함)
        reply_text = await process_with_tools(chat, user_text)

        # "처리 중" 메시지 삭제
        await processing_msg.delete()

        # 응답 전송 (길이 제한 처리)
        if len(reply_text) <= MAX_TELEGRAM_MSG_LEN:
            await update.message.reply_text(reply_text)
        else:
            for i in range(0, len(reply_text), MAX_TELEGRAM_MSG_LEN):
                chunk = reply_text[i : i + MAX_TELEGRAM_MSG_LEN]
                await update.message.reply_text(chunk)

    except Exception as e:
        error_msg = f"⚠️ 오류 발생:\n`{type(e).__name__}: {str(e)[:300]}`"
        logger.error("Error: %s", e, exc_info=True)
        try:
            await processing_msg.edit_text(error_msg, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(error_msg, parse_mode="Markdown")


# ─── 메인 실행 ───────────────────────────────────────────────
def main():
    logger.info("🚀 Gemini AI Agent starting...")
    logger.info("📦 Tools loaded: %d", len(TOOL_DECLARATIONS))

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logger.info("✅ Agent is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
