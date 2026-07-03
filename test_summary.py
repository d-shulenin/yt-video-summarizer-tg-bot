#!/usr/bin/env python3
"""Standalone script for testing the summarization pipeline locally."""

import argparse
import logging
import sys
from transcriber import get_transcript
from summarizer import summarize


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

def main() -> None:
    parser = argparse.ArgumentParser(description="Test YouTube summarization locally")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--template",
        default="templates/obsidian-note.txt",
        help="Path to a custom prompt template (default: templates/obsidian-note.txt)",
    )
    args = parser.parse_args()

    print("⏳ Fetching transcript...")
    try:
        video_info = get_transcript(args.url)
    except ValueError as e:
        logger.error("Failed to fetch transcript: %s", e)
        sys.exit(f"❌ Could not get transcript: {e}")
    except Exception as e:
        logger.exception("Unexpected error fetching transcript")
        sys.exit(f"❌ Unexpected error: {e}")

    print(f"\n📋 Video metadata:")
    print(f"   Title:          {video_info.title}")
    print(f"   Channel:        {video_info.channel}")
    print(f"   Date published: {video_info.date_published or '(unknown)'}")
    print(f"   Duration:       {video_info.duration}s")
    print(f"\n📝 Transcript preview ({len(video_info.transcript)} chars total):")
    print("-" * 60)
    print(video_info.transcript[:500])
    if len(video_info.transcript) > 500:
        print("...")
    print("-" * 60)

    print("\n🧠 Summarizing...")
    try:
        result = summarize(
            video_info.transcript,
            video_url=args.url,
            title=video_info.title,
            channel=video_info.channel,
            channel_url=video_info.channel_url,
            date_published=video_info.date_published,
            template_path=args.template,
        )
    except Exception as e:
        logger.exception("Unexpected error during summarization")
        sys.exit(f"❌ Summarization failed: {e}")

    print("\n📄 Summary:")
    print("=" * 60)
    print(result.text)
    print("=" * 60)

    print(f"\n🤖 Model: {result.model}")
    print(
        f"🪙 Tokens: {result.total_tokens:,} total "
        f"({result.prompt_tokens:,} prompt + {result.completion_tokens:,} completion)"
    )
    if result.estimated_cost_usd is not None:
        print(f"💰 Estimated cost: ${result.estimated_cost_usd:.6f}")
    else:
        print("💰 Price: unknown model — no pricing data")


if __name__ == "__main__":
    main()
