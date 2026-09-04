# Douyin Content Intelligence Lab

This project is a local-first pipeline for collecting authorized Douyin video content and engagement data, then analyzing and producing reviewable short clips.

## Start

```bash
cp .env.example .env
# Replace every CHANGE_ME value before starting services.
docker compose up --build
```

The provider is self-hosted and uses the local `douyin` binary; no external API key is required. Configure `DOUYIN_CLI_PROFILE` for the CLI session and `DOUYIN_COOKIE_FILE` for local `yt-dlp` downloads when protected content requires it.

API: `http://127.0.0.1:8000`

Submit a Douyin video URL:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ingest \
  -H 'content-type: application/json' \
  -d '{"url":"https://www.douyin.com/video/REPLACE_ME"}'
```

The ingest boundary accepts only HTTPS URLs on `douyin.com` or its subdomains. Arbitrary URLs are rejected before they reach local collector/download tools.

Check the job and results:

```bash
curl http://127.0.0.1:8000/api/v1/jobs/1
curl http://127.0.0.1:8000/api/v1/videos
curl http://127.0.0.1:8000/api/v1/videos/1/analysis
curl 'http://127.0.0.1:8000/api/v1/videos/1/comments?limit=100'
```

## Security boundary

The API currently has no application authentication. Docker Compose therefore publishes the API and MinIO console to `127.0.0.1` by default. Do not set `SELF_MEDIA_BIND_ADDRESS=0.0.0.0` or expose these ports to a LAN/public network unless an authenticated reverse proxy or equivalent access-control boundary is in front of them.

`.env`, browser/provider cookies, downloaded media, databases, and local agent/tool state are private runtime material and are excluded from Git. Treat comment `raw_data` and user identifiers returned by the research API as collected data that may contain personal information; do not publish database dumps or API exports without review.

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
