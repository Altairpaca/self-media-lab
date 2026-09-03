import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.analysis import score_video
from app.provider import fetch_data, fetch_hot


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


if __name__ == "__main__":
    unittest.main()
