# Douyin Content Intelligence Lab

This project is a local-first pipeline for collecting authorized Douyin video content and engagement data, then analyzing and producing reviewable short clips.

## Start

```bash
cp .env.example .env
docker compose up --build
```

Before any real collection, change the database and MinIO passwords in `.env`. The provider is self-hosted and uses the local `douyin` binary; no external API key is required. Configure `DOUYIN_CLI_PROFILE` for the CLI session and `DOUYIN_COOKIE_FILE` for local `yt-dlp` downloads when protected content requires it.

API: `http://localhost:8000`

Submit a video URL:

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H 'content-type: application/json' \
  -d '{"url":"https://www.douyin.com/video/REPLACE_ME"}'
```

Check the job and results:

```bash
curl http://localhost:8000/api/v1/jobs/1
curl http://localhost:8000/api/v1/videos
curl http://localhost:8000/api/v1/videos/1/analysis
curl 'http://localhost:8000/api/v1/videos/1/comments?limit=100'
```

## Full video plus engagement data

`yt-dlp` downloads the source video. The self-hosted provider uses `douyin hot`, `douyin video`, and `douyin comments` to collect work and engagement data locally. Protected surfaces can require a fresh browser Cookie; when that session is absent, the provider fails explicitly instead of returning incomplete data as if it were complete.

The public realtime hot board works without a Cookie. Video and comment collection requires a valid local session when Douyin presents its anti-bot challenge.

## Analysis and editing

The worker stores raw media and data, computes engagement and comment metrics, extracts Chinese keywords, optionally transcribes with the included Faster-Whisper dependency, and renders initial 1080x1920 review clips with FFmpeg. Set `ENABLE_TRANSCRIPTION=1` to enable local transcription; the first run downloads the selected model.

This is an analysis and review pipeline. It does not auto-post, evade access controls, or remove rights-management restrictions.

## Reproducible examples

Run the deterministic smoke test:

```bash
python -m unittest discover -s tests -v
```

Fetch the current realtime hot list through the self-hosted provider:

```bash
python scripts/live_example.py --hot-limit 10
```

The same list is available at `GET /api/v1/hot?limit=10`.

Analyze a concrete work from a local session:

```bash
python scripts/live_example.py --video-url 'https://www.douyin.com/video/VIDEO_ID'
```

For an offline repeatable video-analysis example, use the included fixture:

```bash
python scripts/live_example.py --fixture tests/fixtures/sample_video.json
```
