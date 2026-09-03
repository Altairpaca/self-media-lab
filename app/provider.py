"""Self-hosted Douyin provider.

The provider owns the collection process: the only data dependency is the
locally installed ``douyin`` CLI, which reads the same public web surfaces as
a browser. No third-party API key is used. Douyin may still require a fresh
browser cookie for protected video/comment surfaces. The cookie file is used
only by the local yt-dlp download process and is never sent to an external
data service.
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


class ProviderError(RuntimeError):
    pass


def _first(data: dict[str, Any], *keys: str, default=None):
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return default


def _normalize(payload: dict[str, Any], url: str) -> dict[str, Any]:
    payload = payload.get("data", payload) if isinstance(payload, dict) else payload
    video = payload.get("video") or payload.get("work") or payload.get("aweme_detail") or payload
    video = video.get("aweme_detail", video) if isinstance(video, dict) else payload
    stats = video.get("statistics") or video.get("stats") or {}
    author = video.get("author") or {}
    comments = payload.get("comments") or payload.get("comment_list") or []
    return {
        "platform_id": str(_first(video, "aweme_id", "id", "video_id", default="")) or None,
        "source_url": url,
        "title": _first(video, "desc", "title", "caption", default=""),
        "description": _first(video, "desc", "description", default=""),
        "author_id": str(_first(author, "sec_uid", "uid", "id", default="")) or None,
        "author_name": _first(author, "nickname", "name", default=""),
        "duration_seconds": _first(video, "duration", default=None),
        "published_at": _first(video, "create_time", "published_at", default=None),
        "likes": int(_first(stats, "digg_count", "likes", "like_count", default=0) or 0),
        "comments_count": int(_first(stats, "comment_count", "comments", default=len(comments)) or 0),
        "shares": int(_first(stats, "share_count", "shares", default=0) or 0),
        "collects": int(_first(stats, "collect_count", "collects", default=0) or 0),
        "views": int(_first(stats, "play_count", "views", default=0) or 0),
        "comments": comments,
        "raw_data": payload,
    }


def _parse_json(stdout: str) -> Any:
    clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", stdout).strip()
    if not clean:
        return None
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        starts = [index for index in (clean.find("["), clean.find("{")) if index >= 0]
        if starts:
            return json.loads(clean[min(starts):])
        raise


def _cli_json(*args: str) -> Any:
    command = [settings.douyin_cli_path, *args, "-o", "json"]
    if settings.douyin_cli_profile:
        command.extend(["--profile", settings.douyin_cli_profile])
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    except FileNotFoundError as exc:
        raise ProviderError(f"self-hosted provider executable not found: {settings.douyin_cli_path}") from exc
    payload = _parse_json(result.stdout)
    if result.returncode != 0 or payload in (None, [], {}):
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")
        raise ProviderError(detail or f"douyin CLI returned exit code {result.returncode}")
    return payload


def fetch_hot(limit: int = 50, tab: str = "realtime") -> dict[str, Any]:
    """Fetch the current public hot-search billboard through the local CLI."""
    payload = _cli_json("hot", "--tab", tab, "-n", str(limit))
    items = payload if isinstance(payload, list) else payload.get("items", [])
    return {
        "provider": "self-hosted-douyin-cli",
        "tab": tab,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }


def fetch_data(url: str) -> dict[str, Any]:
    """Fetch one work and its comments using the local CLI and local session."""
    video_payload = _cli_json("video", url)
    if isinstance(video_payload, list):
        video_payload = video_payload[0] if video_payload else {}
    normalized = _normalize(video_payload, url)
    comments_payload = _cli_json("comments", url, "-n", "500")
    comments = comments_payload if isinstance(comments_payload, list) else comments_payload.get("comments", [])
    normalized["comments"] = comments
    normalized["comments_count"] = max(normalized["comments_count"], len(comments))
    normalized["raw_data"] = {"video": video_payload, "comments": comments}
    normalized["provider"] = "self-hosted-douyin-cli"
    return normalized


def download_video(url: str, destination: Path) -> tuple[dict[str, Any], Path]:
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "source.%(ext)s"
    command = [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "--merge-output-format", "mp4",
        "-o", str(output),
        "--print-json",
        url,
    ]
    if settings.douyin_cookie_file:
        command[1:1] = ["--cookies", settings.douyin_cookie_file]
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=600)
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    metadata = json.loads(lines[-1]) if lines else {}
    files = [file for file in destination.glob("source.*") if file.suffix not in {".part", ".ytdl"}]
    if not files:
        raise ProviderError("yt-dlp completed without an output video")
    return metadata, files[0]
