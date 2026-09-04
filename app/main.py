from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy import select

from .db import Analysis, Comment, IngestJob, SessionLocal, Video, init_db
from .provider import fetch_hot
from .worker import run_ingest


class IngestRequest(BaseModel):
    url: HttpUrl

    @field_validator("url")
    @classmethod
    def require_douyin_https_url(cls, value: HttpUrl) -> HttpUrl:
        host = (value.host or "").lower().rstrip(".")
        if value.scheme != "https":
            raise ValueError("ingest URL must use HTTPS")
        if host != "douyin.com" and not host.endswith(".douyin.com"):
            raise ValueError("ingest URL must target douyin.com")
        return value


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Douyin Content Intelligence Lab", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/hot")
def hot(limit: int = 50, tab: str = "realtime"):
    return fetch_hot(min(max(limit, 1), 100), tab)


@app.post("/api/v1/ingest", status_code=202)
def ingest(request: IngestRequest):
    session = SessionLocal()
    try:
        job = IngestJob(url=str(request.url))
        session.add(job)
        session.commit()
        session.refresh(job)
        run_ingest.delay(job.id)
        return {"job_id": job.id, "status": job.status}
    finally:
        session.close()


@app.get("/api/v1/jobs/{job_id}")
def job_status(job_id: int):
    session = SessionLocal()
    try:
        job = session.get(IngestJob, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        return {"id": job.id, "url": job.url, "status": job.status, "error": job.error}
    finally:
        session.close()


@app.get("/api/v1/videos")
def videos(limit: int = 50):
    session = SessionLocal()
    try:
        rows = session.scalars(select(Video).order_by(Video.created_at.desc()).limit(min(max(limit, 1), 200))).all()
        return [{"id": row.id, "platform_id": row.platform_id, "title": row.title, "author_name": row.author_name, "likes": row.likes, "comments": row.comments_count, "shares": row.shares, "views": row.views, "video_path": row.video_path} for row in rows]
    finally:
        session.close()


@app.get("/api/v1/videos/{video_id}/analysis")
def video_analysis(video_id: int):
    session = SessionLocal()
    try:
        video = session.get(Video, video_id)
        if not video:
            raise HTTPException(404, "video not found")
        analysis = session.scalar(select(Analysis).where(Analysis.video_id == video_id).order_by(Analysis.created_at.desc()))
        if not analysis:
            raise HTTPException(404, "analysis not ready")
        return {"video_id": video_id, "transcript": analysis.transcript, "keywords": analysis.keywords, "hook_score": analysis.hook_score, "engagement_rate": analysis.engagement_rate, "result": analysis.result}
    finally:
        session.close()


@app.get("/api/v1/videos/{video_id}/comments")
def video_comments(video_id: int, limit: int = 100, offset: int = 0):
    session = SessionLocal()
    try:
        video = session.get(Video, video_id)
        if not video:
            raise HTTPException(404, "video not found")
        rows = session.scalars(
            select(Comment).where(Comment.video_id == video_id).order_by(Comment.likes.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 500))
        ).all()
        return [{
            "id": row.id,
            "platform_id": row.platform_id,
            "user_id": row.user_id,
            "user_name": row.user_name,
            "text": row.text,
            "likes": row.likes,
            "replies_count": row.replies_count,
            "raw_data": row.raw_data,
        } for row in rows]
    finally:
        session.close()
