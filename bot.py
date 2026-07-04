# bot.py
import io
import re
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import config
from transcriber import get_transcript
from summarizer import summarize
from whitelist import whitelist

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

YOUTUBE_URL_RE = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w\-]+"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Send me a YouTube URL and I'll summarize it for you!\n\n"
        "💡 Optional: add custom instructions after the URL to guide the summary."
    )


async def unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❌ You are not authorized to use this bot"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    match = YOUTUBE_URL_RE.search(text)

    if not match:
        await update.message.reply_text(
            "Please send a valid YouTube URL (e.g. https://youtube.com/watch?v=...)"
        )
        return

    url = match.group(0)

    # Extract optional instructions — everything after the URL
    url_end = match.end()
    instructions = text[url_end:].strip()

    await update.message.reply_text("⏳ Fetching transcript, please wait...")

    try:
        video_info = get_transcript(url)
    except ValueError as e:
        await update.message.reply_text(f"❌ Could not get transcript: {e}")
        return
    except Exception as e:
        logger.exception("Unexpected error fetching transcript")
        await update.message.reply_text(f"❌ Unexpected error: {e}")
        return

    await update.message.reply_text("🧠 Summarizing...")

    try:
        result = summarize(
            video_info.transcript,
            video_url=url,
            title=video_info.title,
            channel=video_info.channel,
            channel_url=video_info.channel_url,
            date_published=video_info.date_published,
            instructions=instructions,
        )
    except Exception as e:
        logger.exception("Unexpected error during summarization")
        await update.message.reply_text(f"❌ Summarization failed: {e}")
        return

    # Send summary as a Markdown file named after the video title
    safe_title = re.sub(r"[^\w\s-]", "", video_info.title).strip() or "summary"
    safe_title = re.sub(r"[\s]+", "_", safe_title)
    md_bytes = result.text.encode("utf-8")
    file_obj = io.BytesIO(md_bytes)
    file_obj.name = f"{safe_title}.md"
    await update.message.reply_document(
        document=file_obj,
        caption="📄 Here's your summary",
    )

    # Send price / usage info
    price_lines = [
        f"🤖 Model: `{result.model}`",
        f"🪙 Tokens: {result.total_tokens:,} total  "
        f"({result.prompt_tokens:,} prompt + {result.completion_tokens:,} completion)",
    ]
    if result.estimated_cost_usd is not None:
        price_lines.append(f"💰 Estimated cost: `${result.estimated_cost_usd:.6f}`")
    else:
        price_lines.append("💰 Price: unknown model — no pricing data")

    await update.message.reply_text("\n".join(price_lines))


def run() -> None:
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start, filters=whitelist))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & whitelist, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~whitelist, unauthorized))
    logger.info("Bot started. Polling...")
    app.run_polling()
