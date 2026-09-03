import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import jieba


def media_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def extract_keywords(text: str, limit: int = 30) -> list[dict[str, Any]]:
    words = [word.strip().lower() for word in jieba.lcut(text) if len(word.strip()) > 1]
    stop = {"这个", "那个", "我们", "你们", "他们", "然后", "所以", "真的", "就是", "可以", "一个"}
    counts = Counter(word for word in words if word not in stop and not re.fullmatch(r"[\W_]+", word))
    return [{"keyword": word, "count": count} for word, count in counts.most_common(limit)]


def comment_stats(comments: list[dict[str, Any]]) -> dict[str, Any]:
    if not comments:
        return {"count": 0, "avg_likes": 0, "top_comments": []}
    ranked = sorted(comments, key=lambda item: int(item.get("likes", item.get("digg_count", 0)) or 0), reverse=True)
    return {
        "count": len(comments),
        "avg_likes": round(sum(int(item.get("likes", item.get("digg_count", 0)) or 0) for item in comments) / len(comments), 2),
        "top_comments": [
            {"text": item.get("text", item.get("content", "")), "likes": int(item.get("likes", item.get("digg_count", 0)) or 0)}
            for item in ranked[:20]
        ],
    }


def score_video(video: dict[str, Any], comments: list[dict[str, Any]], transcript: str = "") -> dict[str, Any]:
    views = max(int(video.get("views", 0) or 0), 1)
    interactions = sum(int(video.get(key, 0) or 0) for key in ("likes", "comments_count", "shares", "collects"))
    engagement_rate = round(interactions / views, 6) if video.get("views") else None
    comment_text = " ".join(str(item.get("text", item.get("content", ""))) for item in comments)
    corpus = " ".join(filter(None, [video.get("title", ""), video.get("description", ""), transcript, comment_text]))
    keywords = extract_keywords(corpus) if corpus else []
    hook_terms = ("为什么", "如何", "千万", "真相", "别再", "原来", "一定要", "曝光", "翻车")
    hook_score = min(100.0, sum(12 for term in hook_terms if term in str(video.get("title", ""))) + min(len(comments), 40))
    return {
        "engagement_rate": engagement_rate,
        "interaction_total": interactions,
        "comment_stats": comment_stats(comments),
        "keywords": keywords,
        "hook_score": hook_score,
        "signals": {
            "has_transcript": bool(transcript),
            "has_comments": bool(comments),
            "comment_density": round(len(comments) / max(views, 1), 8) if video.get("views") else None,
        },
    }
