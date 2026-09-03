import json
import subprocess
from pathlib import Path

from sqlalchemy import select

from .analysis import media_duration, score_video
from .config import settings
from .db import Analysis, Clip, Comment, IngestJob, SessionLocal, Video
from .provider import download_video, fetch_data


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _run_transcription(path: Path) -> tuple[str, list[dict]]:
    if not settings.enable_transcription:
        return "", []
    try:
        from faster_whisper import WhisperModel  # optional, intentionally loaded only when enabled
    except ImportError:
        return "", []
    model = WhisperModel(settings.whisper_model, compute_type="int8")
    segments, _ = model.transcribe(str(path), vad_filter=True)
    rows = [{"start": segment.start, "end": segment.end, "text": segment.text.strip()} for segment in segments]
    return " ".join(row["text"] for row in rows), rows


def _make_clips(video: Video, analysis: Analysis, root: Path) -> None:
    duration = analysis.duration_seconds or video.duration_seconds or 0
    if duration <= 0:
        return
    segments = analysis.transcript_segments or []
    ranges = []
    if segments:
        for segment in segments:
            text = segment.get("text", "")
            score = sum(text.count(term) for term in ("但是", "为什么", "真相", "结果", "原来", "所以"))
            if score or len(ranges) < 3:
                start = max(0.0, float(segment["start"]) - 3)
                end = min(duration, max(float(segment["end"]) + 12, start + 15))
                ranges.append((start, end, float(score + len(text) / 80)))
    if not ranges:
        clip_len = min(45.0, duration)
        ranges = [(start, min(start + clip_len, duration), max(0.0, duration - start)) for start in (0.0, max(0.0, duration / 2 - clip_len / 2))]
    for index, (start, end, score) in enumerate(ranges[:5]):
        output = root / f"clip-{index + 1}.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(start), "-i", str(video.video_path), "-t", str(end - start),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-movflags", "+faststart", str(output),
        ], check=True, capture_output=True)
        analysis_session = SessionLocal()
        try:
            analysis_session.add(Clip(video_id=video.id, start_seconds=start, end_seconds=end, score=score, output_path=str(output), status="ready"))
            analysis_session.commit()
        finally:
            analysis_session.close()


def ingest_job(job_id: int) -> None:
    session = SessionLocal()
    job = session.get(IngestJob, job_id)
    if not job:
        session.close()
        return
    job.status = "running"
    session.commit()
    try:
        provider_data = fetch_data(job.url)
        workdir = Path(settings.media_root) / f"job-{job_id}"
        yt_metadata, video_path = download_video(job.url, workdir)
        normalized = provider_data if provider_data.get("platform_id") else {
            "platform_id": str(yt_metadata.get("id", "")) or None,
            "source_url": job.url,
            "title": yt_metadata.get("title", ""),
            "description": yt_metadata.get("description", ""),
            "author_id": yt_metadata.get("channel_id"),
            "author_name": yt_metadata.get("uploader", ""),
            "duration_seconds": yt_metadata.get("duration"),
            "likes": _int(yt_metadata.get("like_count")),
            "comments_count": _int(yt_metadata.get("comment_count")),
            "shares": 0, "collects": 0, "views": _int(yt_metadata.get("view_count")),
            "comments": [], "raw_data": yt_metadata,
        }
        existing = session.scalar(select(Video).where(Video.platform_id == normalized.get("platform_id"))) if normalized.get("platform_id") else None
        video = existing or Video(platform_id=normalized.get("platform_id"), source_url=job.url)
        for key in ("title", "description", "author_id", "author_name", "duration_seconds", "likes", "comments_count", "shares", "collects", "views", "raw_data"):
            if normalized.get(key) is not None:
                setattr(video, key, normalized[key])
        video.video_path = str(video_path)
        session.add(video)
        session.flush()
        for item in normalized.get("comments", []):
            session.add(Comment(
                video_id=video.id,
                platform_id=str(item.get("cid", item.get("comment_id", ""))) or None,
                user_id=str((item.get("user") or {}).get("uid", item.get("user_id", ""))) or None,
                user_name=(item.get("user") or {}).get("nickname", item.get("user_name", "")),
                text=item.get("text", item.get("content", "")),
                likes=_int(item.get("likes", item.get("digg_count"))),
                replies_count=_int(item.get("reply_count", item.get("replies_count"))),
                raw_data=item,
            ))
        session.commit()
        duration = media_duration(video_path)
        transcript, segments = _run_transcription(video_path)
        comment_rows = session.scalars(select(Comment).where(Comment.video_id == video.id)).all()
        comments = [{"text": row.text, "likes": row.likes} for row in comment_rows]
        result = score_video({"title": video.title, "description": video.description, "likes": video.likes, "comments_count": video.comments_count, "shares": video.shares, "collects": video.collects, "views": video.views}, comments, transcript)
        analysis = Analysis(video_id=video.id, transcript=transcript, transcript_segments=segments, duration_seconds=duration, engagement_rate=result["engagement_rate"], comment_sentiment={"status": "pending", "note": "Connect a Chinese sentiment model for production scoring."}, keywords=result["keywords"], hook_score=result["hook_score"], result=result)
        session.add(analysis)
        video.duration_seconds = duration
        session.commit()
        _make_clips(video, analysis, workdir)
        job.status = "completed"
        session.commit()
    except Exception as exc:
        session.rollback()
        job.status = "failed"
        job.error = str(exc)
        session.commit()
        raise
    finally:
        session.close()
