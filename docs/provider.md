# Self-hosted Provider

The provider uses the locally installed `douyin` CLI. No external API key is
required.

```text
hot <-> current public hot-search billboard
video <url|id> <-> one work record
comments <url|id> <-> paginated comments
```

The application invokes these commands with `-o json`, stores the raw JSON,
and normalizes work statistics into the database. The Docker image builds the
CLI from `github.com/tamnd/douyin-cli`.

## Session behavior

The realtime hot billboard works without a Cookie. Douyin can require a fresh
browser Cookie for video, search, creator, and comment surfaces. Set
`DOUYIN_CLI_PROFILE` for the CLI's native `--profile` option. The
`DOUYIN_COOKIE_FILE` setting is used by the local `yt-dlp` download process;
the current CLI does not expose a Cookie flag. Both paths remain local and
are still subject to Douyin's own access controls. If Douyin returns an
anti-bot challenge, the provider raises an error instead of silently storing
incomplete data.

## Normalized work shape

```json
{
  "platform_id": "123",
  "source_url": "https://www.douyin.com/video/123",
  "title": "...",
  "author_name": "...",
  "duration_seconds": 32.5,
  "likes": 1000,
  "comments_count": 80,
  "shares": 30,
  "collects": 50,
  "views": 20000,
  "comments": [
    {"text": "...", "likes": 12, "replies_count": 3}
  ],
  "raw_data": {}
}
```

Only collect content and data the operator is authorized to access, and
respect platform terms, privacy requirements, rate limits, and copyright
rules.
