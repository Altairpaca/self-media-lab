import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.analysis import score_video
from app.db import Base, Comment, IngestJob, Video
from app.main import IngestRequest
from app.provider import fetch_data, fetch_hot
from app.pipeline import ingest_job


class ProviderSmokeTest(unittest.TestCase):
    def test_hot_and_video_provider_contract(self):
        hot_payload = [{"rank": 1, "word": "测试热点", "hot_value": 123456, "url": "https://www.douyin.com/search/测试热点"}]
        video_payload = {
            "aweme_id": "123",
            "desc": "为什么要做小样本验证？",
            "author": {"nickname": "测试账号"},
            "statistics": {"digg_count": 100, "comment_count": 8, "share_count": 3, "collect_count": 5, "play_count": 1000}
        }
        comments_payload = [{"text": "这条建议很实用", "digg_count": 12}]

        def fake_run(command, **_):
            if command[1] == "hot":
                return type("Result", (), {"returncode": 0, "stdout": json.dumps(hot_payload), "stderr": ""})()
            if command[1] == "video":
                return type("Result", (), {"returncode": 0, "stdout": json.dumps(video_payload), "stderr": ""})()
            return type("Result", (), {"returncode": 0, "stdout": json.dumps(comments_payload), "stderr": ""})()

        with patch("app.provider.subprocess.run", side_effect=fake_run):
            hot = fetch_hot(1)
            video = fetch_data("https://www.douyin.com/video/123")

        self.assertEqual(hot["items"][0]["word"], "测试热点")
        self.assertEqual(video["platform_id"], "123")
        self.assertEqual(video["likes"], 100)
        self.assertEqual(video["comments"][0]["text"], "这条建议很实用")

    def test_fixture_analysis_is_reproducible(self):
        fixture = json.loads(Path("tests/fixtures/sample_video.json").read_text(encoding="utf-8"))
        result = score_video(fixture, fixture["comments"])
        self.assertEqual(result["interaction_total"], 15856)
        self.assertEqual(result["engagement_rate"], 0.085247)
        self.assertGreater(result["hook_score"], 0)
        self.assertTrue(result["keywords"])

    def test_ingest_accepts_only_https_douyin_urls(self):
        request = IngestRequest(url="https://v.douyin.com/example/")
        self.assertEqual(request.url.host, "v.douyin.com")

        for unsafe_url in (
            "http://www.douyin.com/video/123",
            "https://example.com/video/123",
            "http://127.0.0.1:9000/internal",
        ):
            with self.subTest(url=unsafe_url), self.assertRaises(ValidationError):
                IngestRequest(url=unsafe_url)

    def test_ingest_reuses_existing_comment_platform_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "media_lab.sqlite3"
            engine = create_engine(f"sqlite:///{database}", connect_args={"check_same_thread": False})
            Base.metadata.create_all(engine)
            test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            provider_data = {
                "platform_id": "video-1",
                "source_url": "https://www.douyin.com/video/1",
                "title": "测试视频",
                "description": "",
                "author_id": None,
                "author_name": "测试账号",
                "duration_seconds": 1,
                "likes": 1,
                "comments_count": 1,
                "shares": 0,
                "collects": 0,
                "views": 10,
                "comments": [{"cid": "comment-1", "text": "同一条评论"}],
                "raw_data": {},
            }
            with test_sessions() as session:
                session.add_all([IngestJob(url=provider_data["source_url"]) for _ in range(2)])
                session.commit()
                job_ids = [job.id for job in session.query(IngestJob).order_by(IngestJob.id)]

            with (
                patch("app.pipeline.SessionLocal", test_sessions),
                patch("app.pipeline.fetch_data", return_value=provider_data),
                patch("app.pipeline.download_video", return_value=({}, database)),
                patch("app.pipeline.media_duration", return_value=1),
                patch("app.pipeline._run_transcription", return_value=("", [])),
                patch("app.pipeline._make_clips"),
            ):
                ingest_job(job_ids[0])
                ingest_job(job_ids[1])

            with test_sessions() as session:
                self.assertEqual(session.query(Video).count(), 1)
                self.assertEqual(session.query(Comment).count(), 1)


if __name__ == "__main__":
    unittest.main()
