from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class IngestJob(Base):
    __tablename__ = "ingest_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Video(Base):
    __tablename__ = "videos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(32), default="douyin", index=True)
    platform_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    source_url: Mapped[str] = mapped_column(String(2000))
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[str | None] = mapped_column(String(128), index=True)
    author_name: Mapped[str | None] = mapped_column(String(256))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    collects: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    video_path: Mapped[str | None] = mapped_column(String(2000))
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    comments: Mapped[list["Comment"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform_id: Mapped[str | None] = mapped_column(String(128), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128))
    user_name: Mapped[str | None] = mapped_column(String(256))
    text: Mapped[str] = mapped_column(Text)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    replies_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    video: Mapped[Video] = relationship(back_populates="comments")


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    transcript: Mapped[str | None] = mapped_column(Text)
    transcript_segments: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    engagement_rate: Mapped[float | None] = mapped_column(Float)
    comment_sentiment: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    keywords: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    hook_score: Mapped[float | None] = mapped_column(Float)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    video: Mapped[Video] = relationship(back_populates="analyses")


class Clip(Base):
    __tablename__ = "clips"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float, default=0)
    output_path: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(32), default="queued")


def init_db() -> None:
    Base.metadata.create_all(engine)
