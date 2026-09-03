#!/usr/bin/env python3
"""Fetch the current hot list and analyze one concrete video or fixture."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis import score_video
from app.provider import fetch_data, fetch_hot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hot-limit", type=int, default=10)
    parser.add_argument("--video-url")
    parser.add_argument("--fixture", default="tests/fixtures/sample_video.json")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    hot = fetch_hot(args.hot_limit)
    print("=== latest realtime hot list ===")
    print(json.dumps(hot, ensure_ascii=False, indent=2))

    if args.video_url:
        print("=== live video analysis ===")
        data = fetch_data(args.video_url)
        comments = data.get("comments", [])
        analysis = score_video(data, comments)
        print(json.dumps({"video": data, "analysis": analysis}, ensure_ascii=False, indent=2))
    elif args.fixture:
        fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        comments = fixture.pop("comments", [])
        print("=== reproducible fixture video analysis ===")
        print(json.dumps({"video": fixture, "analysis": score_video(fixture, comments)}, ensure_ascii=False, indent=2))

    if args.out:
        args.out.write_text(json.dumps(hot, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
