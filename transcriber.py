from dataclasses import dataclass
from typing import Optional
import logging
import re
import yt_dlp
import config


logger = logging.getLogger(__name__)

_SUBTITLE_EXTS_PRIORITY = ("vtt", "json3")
_SUBTITLES_LANGS = ['en', 'ru']

@dataclass
class VideoInfo:
    transcript: str
    title: str
    channel: str
    date_published: str   # ISO-8601 (YYYY-MM-DD), empty string if unknown
    duration: Optional[int]  # seconds

def get_transcript(url: str) -> VideoInfo:
    """
    Download auto-generated or manual subtitles from a YouTube video.
    Tries English first, then falls back to Russian.
    Returns a VideoInfo dataclass with the transcript text and video metadata.
    Raises ValueError if neither language has subtitles.
    """
    logger.info("Fetching transcript for %s", url)

    ydl_opts = {
        "skip_download": True,
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": _SUBTITLES_LANGS,
        "subtitlesformat": "vtt",
        "quiet": True,
        "no_warnings": True,
    }
    if config.YTDLP_COOKIES_FILE:
        ydl_opts["cookiefile"] = config.YTDLP_COOKIES_FILE
        logger.debug("Using cookies file: %s", config.YTDLP_COOKIES_FILE)

    logger.debug("Extracting video info via yt-dlp")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get("title") or ""
    channel = info.get("channel") or info.get("uploader") or ""
    duration = info.get("duration")
    raw_date = info.get("upload_date") or ""  # YYYYMMDD from yt-dlp
    date_published = _format_date(raw_date)
    logger.info("Video: %s (%ss)", title or "<no title>", duration or "?")

    subtitles = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}

    for lang in _SUBTITLES_LANGS:
        tracks = subtitles.get(lang) or auto_subs.get(lang) or []
        text_track = _pick_best_track(tracks)
        if text_track:
            kind = "manual" if subtitles.get(lang) else "auto"
            logger.info("Found %s subtitle track (%s)", kind, lang)
            ext = text_track.get("ext", "unknown")
            logger.info("Selected subtitle format: %s", ext)

            logger.debug("Downloading %s subtitle data", lang)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                resp = ydl.urlopen(text_track["url"])
                raw = resp.read().decode("utf-8")

            logger.debug("Downloaded %d bytes of subtitle data", len(raw))

            cleaned = _clean_vtt(raw)
            logger.info("Transcript ready: %d characters (%s)", len(cleaned), lang)
            return VideoInfo(
                transcript=cleaned,
                title=title,
                channel=channel,
                date_published=date_published,
                duration=duration,
            )

    raise ValueError(f"No English or Russian subtitles found for: {url}")


def _format_date(raw: str) -> str:
    """Convert yt-dlp YYYYMMDD string to ISO-8601 YYYY-MM-DD, or return empty string."""
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw  # already formatted or empty


def _pick_best_track(tracks: list[dict]) -> Optional[dict]:
    """Pick the best available track by preferred format order."""
    if not tracks:
        return None
    for ext in _SUBTITLE_EXTS_PRIORITY:
        track = next((t for t in tracks if t.get("ext") == ext), None)
        if track:
            return track
    return tracks[0]


def _clean_vtt(vtt_text: str) -> str:
    """Strip VTT timing markup and return plain transcript text."""
    logger.debug("Cleaning VTT markup")
    lines = []
    for line in vtt_text.splitlines():
        if (
            line.startswith("WEBVTT")
            or "-->" in line
            or line.strip() == ""
            or re.match(r"^\d+$", line.strip())
            or line.startswith("Kind:")
            or line.startswith("Language:")
        ):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            lines.append(line)

    # Deduplicate consecutive identical lines (common in auto-captions)
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)

    logger.debug("Removed %d duplicate lines", len(lines) - len(deduped))
    return "\n".join(deduped)
