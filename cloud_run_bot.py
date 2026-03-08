from fastapi import FastAPI, Request
import google.generativeai as genai
import logging
import os
import json
from dotenv import load_dotenv
from pathlib import Path
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, Application

from tools import TOOL_DECLARATIONS, execute_tool

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# 설정 로드 (dotenv)
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_CHAT_ID = os.getenv("CHAT_ID")
BKIT_PATH = os.getenv("BKIT_PATH")

genai.configure(api_key=GEMINI_API_KEY)

# 시스템 프롬프트 로드
SYSTEM_PROMPT = ""
try:
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    SYSTEM_PROMPT = "You are a helpful AI assistant."

if BKIT_PATH:
    bkit_gemini_md = Path(BKIT_PATH) / "GEMINI.md"
    if bkit_gemini_md.exists():
        SYSTEM_PROMPT += "\n\n" + "="*40 + "\n"
        SYSTEM_PROMPT += "## bkit Core Instructions\n"
        SYSTEM_PROMPT += bkit_gemini_md.read_text(encoding="utf-8")
        SYSTEM_PROMPT += "\n" + "="*40 + "\n"

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
    "gemini-2.0-flash",
    system_instruction=SYSTEM_PROMPT,
    tools=[tools_proto],
)
chat_sessions = {}
MAX_TELEGRAM_MSG_LEN = 4096
MAX_TOOL_ITERATIONS = 15

app = FastAPI()

ptb_app: Application = None

def is_authorized(update: Update) -> bool:
    if ALLOWED_CHAT_ID in (None, "", "YOUR_CHAT_ID") or ALLOWED_CHAT_ID is None:
        return True
    return str(update.effective_chat.id) == str(ALLOWED_CHAT_ID)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    welcome = f"🤖 **Gemini Bot(Cloud Run 버젼)** 활성화 완료!\n💡 당신의 Chat ID: `{chat_id}`\n\nPC가 꺼져있어도 언제든 대답할 수 있습니다!"
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def process_with_tools(chat, user_text: str) -> str:
    response = chat.send_message(user_text)

    for iteration in range(MAX_TOOL_ITERATIONS):
        if not response.candidates:
            return "⚠️ 응답을 생성하지 못했습니다."
            
        candidate = response.candidates[0]
        parts = candidate.content.parts

        function_calls = [p for p in parts if p.function_call.name]

        if not function_calls:
            text_parts = [p.text for p in parts if p.text]
            return "\n".join(text_parts) if text_parts else "⚠️ 응답을 생성할 수 없습니다."

        function_responses = []
        for fc in function_calls:
            tool_name = fc.function_call.name
            tool_args = dict(fc.function_call.args) if fc.function_call.args else {}

            logger.info("🔧 Tool call: %s(%s)", tool_name, tool_args)

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

        response = chat.send_message(
            genai.protos.Content(parts=function_responses)
        )

    return "⚠️ 도구 호출이 최대 횟수를 초과했습니다."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    user_text = update.message.text
    chat_id = update.effective_chat.id
    processing_msg = await update.message.reply_text("⏳ 처리 중...")

    try:
        if chat_id not in chat_sessions:
            chat_sessions[chat_id] = model.start_chat(history=[], enable_automatic_function_calling=False)
        chat = chat_sessions[chat_id]
        
        reply_text = await process_with_tools(chat, user_text)
        
        await processing_msg.delete()
        
        if len(reply_text) <= MAX_TELEGRAM_MSG_LEN:
            await update.message.reply_text(reply_text)
        else:
            for i in range(0, len(reply_text), MAX_TELEGRAM_MSG_LEN):
                await update.message.reply_text(reply_text[i : i + MAX_TELEGRAM_MSG_LEN])
    except Exception as e:
        error_msg = f"⚠️ 오류가 발생했습니다.\n`{str(e)[:200]}`"
        try:
            await processing_msg.edit_text(error_msg, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(error_msg, parse_mode="Markdown")

@app.on_event("startup")
async def startup_event():
    global ptb_app
    logger.info("Starting Telegram Bot application...")
    ptb_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    ptb_app.add_handler(CommandHandler("start", start_command))
    ptb_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    await ptb_app.initialize()
    await ptb_app.start()
    
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    if webhook_url:
        await ptb_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to {webhook_url}")

@app.on_event("shutdown")
async def shutdown_event():
    global ptb_app
    if ptb_app:
        await ptb_app.stop()
        await ptb_app.shutdown()

@app.post("/")
async def process_webhook(request: Request):
    """텔레그램에서 보내는 웹훅 요청을 처리합니다."""
    global ptb_app
    if ptb_app:
        try:
            data = await request.json()
            update = Update.de_json(data, ptb_app.bot)
            await ptb_app.process_update(update)
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return {"status": "error"}
    return {"status": "not_initialized"}

@app.get("/health")
def health_check():
    """Cloud Run 등의 헬스 체크용 엔드포인트입니다."""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

