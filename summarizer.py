# summarizer.py
import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI
import config
import time


logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 86400  # 1 day

# Cached pricing data: (timestamp, {model_id → (prompt, completion)})
_pricing_cache: Optional[tuple[float, dict[str, tuple[float, float]]]] = None

_client = OpenAI(
    api_key=config.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)


@dataclass
class SummaryResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: Optional[float]
    model: str


def summarize(
    transcript: str,
    video_url: str = "",
    title: str = "",
    channel: str = "",
    channel_url: str = "",
    date_published: str = "",
    instructions: str = "",
    template_path: str = "templates/obsidian-note.txt",
) -> SummaryResult:
    """
    Read the plain-text prompt template, substitute all placeholders
    ({transcript}, {video_id}, {title}, {channel}, {date_published}),
    call OpenRouter, and return the summary with token usage / price info.
    """
    template = Path(template_path).read_text(encoding="utf-8")

    video_id = _extract_video_id(video_url)

    # Build the YouTube Video Information block that goes into the prompt
    info_lines = []
    if title:
        info_lines.append(f"Title: {title}")
    if channel:
        info_lines.append(f"Channel: {channel}")
    if date_published:
        info_lines.append(f"Date Published: {date_published}")
    if video_id:
        info_lines.append(f"URL: https://www.youtube.com/watch?v={video_id}")
    video_info_block = "\n".join(info_lines) if info_lines else "(no metadata available)"

    prompt = template.replace("{transcript}", transcript)
    prompt = prompt.replace("{video_info}", video_info_block)
    prompt = prompt.replace("{title}", title)
    prompt = prompt.replace("{channel}", channel)
    prompt = prompt.replace("{channel_url}", channel_url)
    prompt = prompt.replace("{date_published}", date_published)
    prompt = prompt.replace("{instructions}", instructions if instructions else "(none — generate a standard summary)")

    if video_id:
        # Pre-process: give the model a concrete example in the prompt
        prompt = prompt.replace("{video_id}", video_id)

    logger.info("Sending prompt to %s (%d characters)", config.OPENROUTER_MODEL, len(prompt))

    response = _client.chat.completions.create(
        model=config.OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )

    summary_text = response.choices[0].message.content.strip()

    # Post-process: ensure the video ID is substituted even if the model output
    # still contains the literal placeholder.
    if video_id:
        summary_text = summary_text.replace("{video_id}", video_id)

    # Token usage
    usage = response.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else 0

    # Estimate cost from live OpenRouter pricing
    cost = _estimate_cost(config.OPENROUTER_MODEL, prompt_tokens, completion_tokens)
    if cost is not None:
        logger.info("LLM call cost estimate: $%.9f", cost)

    return SummaryResult(
        text=summary_text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=cost,
        model=config.OPENROUTER_MODEL,
    )


def _extract_video_id(url: str) -> str:
    """Extract the 11-character YouTube video ID from a URL."""
    match = re.search(r"(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else ""


def _fetch_model_pricing() -> dict[str, tuple[float, float]]:
    global _pricing_cache
    now = time.time()

    if _pricing_cache is not None:
        cached_at, data = _pricing_cache
        if now - cached_at < _CACHE_TTL_SECONDS:
            logger.debug("Using cached pricing (%.0fh old)", (now - cached_at) / 3600)
            return data
        logger.debug("Pricing cache expired, refetching")

    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        pricing: dict[str, tuple[float, float]] = {}
        for model in data.get("data", []):
            model_id = model.get("id")
            p = model.get("pricing", {})
            if model_id and "prompt" in p and "completion" in p:
                pricing[model_id] = (float(p["prompt"]), float(p["completion"]))

        logger.info("Fetched pricing for %d models from OpenRouter", len(pricing))
        _pricing_cache = (now, pricing)
        return pricing
    except (urllib.error.URLError, json.JSONDecodeError, ValueError) as e:
        logger.warning("Failed to fetch OpenRouter pricing: %s", e)
        if _pricing_cache is not None:
            logger.warning("Falling back to stale cached pricing")
            return _pricing_cache[1]
        _pricing_cache = (now, {})
        return {}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """Return estimated USD cost based on live OpenRouter pricing."""
    pricing = _fetch_model_pricing()
    prices = pricing.get(model)
    if not prices:
        return None

    prompt_price, completion_price = prices
    return prompt_tokens * prompt_price + completion_tokens * completion_price
