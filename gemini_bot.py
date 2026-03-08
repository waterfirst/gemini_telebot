"""
Gemini Telegram Bot
- 텔레그램 메시지를 Gemini API로 전달하고 응답을 반환합니다.
- chat_id 기반 보안 필터를 포함합니다.
"""

import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# ─── 로깅 설정 ───────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── 설정 로드 (dotenv) ───────────────────────────────────────
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_CHAT_ID = os.getenv("CHAT_ID")  # 보안: 허용된 chat_id

# ─── Gemini 초기화 ──────────────────────────────────────────
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# 대화 히스토리를 유지하기 위한 채팅 세션
chat_sessions: dict = {}

# ─── 텔레그램 메시지 최대 길이 ──────────────────────────────
MAX_TELEGRAM_MSG_LEN = 4096


# ─── 보안 필터: chat_id 확인 ─────────────────────────────────
def is_authorized(update: Update) -> bool:
    """허용된 chat_id인지 확인합니다."""
    if ALLOWED_CHAT_ID in (None, "", "YOUR_CHAT_ID"):
        return True  # chat_id가 미설정이면 모두 허용 (초기 설정용)
    return str(update.effective_chat.id) == str(ALLOWED_CHAT_ID)


# ─── /start 명령어 ───────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """봇 시작 시 환영 메시지와 chat_id를 표시합니다."""
    chat_id = update.effective_chat.id
    welcome = (
        "🤖 **Gemini 텔레그램 비서**가 활성화되었습니다!\n\n"
        f"📌 당신의 Chat ID: `{chat_id}`\n\n"
        "이 Chat ID를 `config.json`의 `chat_id` 항목에 입력하면\n"
        "보안 필터가 활성화됩니다.\n\n"
        "💬 아무 메시지나 보내보세요!"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


# ─── /reset 명령어 ───────────────────────────────────────────
async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """대화 히스토리를 초기화합니다."""
    chat_id = update.effective_chat.id
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]
    await update.message.reply_text("🔄 대화 히스토리가 초기화되었습니다.")


# ─── 메시지 처리 ─────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """사용자 메시지를 Gemini에게 전달하고 응답을 반환합니다."""
    # 보안 확인
    if not is_authorized(update):
        logger.warning(
            "Unauthorized access attempt from chat_id: %s",
            update.effective_chat.id,
        )
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id
    logger.info("Message from %s: %s", chat_id, user_text[:50])

    try:
        # 채팅 세션 가져오기 또는 새로 생성
        if chat_id not in chat_sessions:
            chat_sessions[chat_id] = model.start_chat(history=[])

        chat = chat_sessions[chat_id]

        # Gemini에게 메시지 전달
        response = chat.send_message(user_text)
        reply_text = response.text

        # 텔레그램 메시지 길이 제한 처리 (4096자)
        if len(reply_text) <= MAX_TELEGRAM_MSG_LEN:
            await update.message.reply_text(reply_text)
        else:
            # 긴 메시지는 분할 전송
            for i in range(0, len(reply_text), MAX_TELEGRAM_MSG_LEN):
                chunk = reply_text[i : i + MAX_TELEGRAM_MSG_LEN]
                await update.message.reply_text(chunk)

    except Exception as e:
        error_msg = f"⚠️ 오류가 발생했습니다:\n`{type(e).__name__}: {str(e)[:200]}`"
        logger.error("Error processing message: %s", e, exc_info=True)
        await update.message.reply_text(error_msg, parse_mode="Markdown")


# ─── 메인 실행 ───────────────────────────────────────────────
def main():
    """봇을 시작합니다."""
    logger.info("🚀 Gemini Telegram Bot starting...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # 핸들러 등록
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logger.info("✅ Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
