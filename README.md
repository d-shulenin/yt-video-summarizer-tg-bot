# YouTube Video Summarizer Telegram Bot

Telegram bot that summarizes YouTube videos using yt-dlp and OpenRouter.

## Setup

1. Clone the repo
2. Install dependencies: `uv sync`
3. Copy env file: `cp .env.example .env` and fill in values
4. Run: `uv run python main.py`

## Running with Docker Compose

Docker Compose is the recommended way to run the bot. It mounts your `.env` file and `cookies.txt` directly without baking them into the image.

### 1. Prepare your `.env` file

Make sure `YTDLP_COOKIES_FILE` points to the path **inside** the container:

```bash
# .env
TELEGRAM_BOT_TOKEN=your_token
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=openai/gpt-4o-mini
YTDLP_COOKIES_FILE=/app/cookies.txt
```

### 2. Create `docker-compose.yml`

```yaml
services:
  bot:
    build: .
    env_file: .env
    volumes:
      - ./cookies.txt:/app/cookies.txt
    restart: unless-stopped
```

### 3. Start the bot

```bash
# Build and start in the background
docker compose up --build -d

# View logs
docker compose logs -f bot

# Stop
docker compose down
```

### Rebuilding after code changes

```bash
docker compose up --build -d
```

### Why Compose over plain `docker run`?

- **No secrets in image layers**: `.env` and `cookies.txt` are mounted at runtime, never copied into the build.
- **One command**: `docker compose up -d` handles build, env vars, volumes, and restart policy.
- **Easy logs**: `docker compose logs -f` streams output from the running container.

## Running with Docker (manual)

```bash
# Build the image
docker build -t yt-summarizer-bot .

# Run the container (mount env and cookies separately)
docker run -d \
  --env-file .env \
  -v "$(pwd)/cookies.txt:/app/cookies.txt" \
  yt-summarizer-bot
```

## Testing summarization locally

Before running the full Telegram bot, you can test the summarization pipeline with a single command:

```bash
uv run python test_summary.py "https://www.youtube.com/watch?v=<VIDEO_ID>"
```

The script will:

1. Fetch the transcript from the video
2. Print the first 500 characters of the transcript
3. Send it to OpenRouter for summarization
4. Print the resulting summary and token usage / estimated cost

Optional flags:

| Flag              | Description                                                     |
| ----------------- | --------------------------------------------------------------- |
| `--template PATH` | Use a custom prompt template instead of `templates/obsidian-note.txt` |

Example with custom template:

```bash
uv run python test_summary.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --template templates/my-template.txt
```

## Configuration

| Variable             | Description                                                           |
| -------------------- | --------------------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather)                             |
| `OPENROUTER_API_KEY` | From [openrouter.ai/keys](https://openrouter.ai/keys)                 |
| `OPENROUTER_MODEL`   | Optional, default `openai/gpt-4o-mini`                                |
| `YTDLP_COOKIES_FILE` | Optional, path to a Netscape-format cookies file (e.g. `cookies.txt`) |

## Exporting cookies

YouTube may block yt-dlp without valid cookies. Export them from your browser with the [cookies.txt extension](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) and save the file as `cookies.txt` in the project root, then set `YTDLP_COOKIES_FILE=cookies.txt` in `.env`.

## How the bot replies

When you send a YouTube URL in Telegram, the bot replies with:

1. A `summary.md` file containing the full summary text
2. A follow-up message with token usage and estimated cost:

```
🤖 Model: openai/gpt-4o-mini
🪙 Tokens: 12,345 total (10,000 prompt + 2,345 completion)
💰 Estimated cost: $0.003210
```

Cost estimation is based on known per-token pricing. If your model isn't in the built-in pricing table, the cost line will say "unknown model — no pricing data".
