# OpenClaw Newsroom

AI/tech news scanning and curation pipeline powered by Microsoft Agent Framework (MAF).

Scans multiple sources, scores and deduplicates articles, curates top stories with AI, and generates a formatted daily digest.

## Pipeline

```
RSS feeds ──┐
Tavily ─────┤
GitHub ─────┼── Scanner Agent ── Editor Agent ── Writer Agent ── Digest
Reddit ─────┘   (collects)       (scores/dedup)   (formats)
```

**80 articles → 15 curated → formatted digest in ~6 minutes**

## Quick Start

```bash
# Clone and install
git clone https://github.com/ShonP/newsroom.git
cd newsroom
uv sync

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
uv run newsroom digest     # Full pipeline: scan → curate → write
uv run newsroom scan       # Scan only (raw articles JSON)
```

## Configuration

Create a `.env` file:

```env
# Required
AZURE_API_KEY=your-azure-openai-key
OPENAI_BASE_URL=https://your-endpoint.openai.azure.com/openai/v1/
TAVILY_API_KEY=your-tavily-key

# Optional
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret
```

### API Keys

| Key | Where to get it | Required |
|-----|-----------------|----------|
| `AZURE_API_KEY` | [Azure Portal](https://portal.azure.com) → Cognitive Services | ✅ |
| `OPENAI_BASE_URL` | Azure OpenAI resource endpoint | ✅ |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com) (free: 1K queries/month) | ✅ |
| `REDDIT_CLIENT_ID` | [reddit.com/prefs/apps](https://reddit.com/prefs/apps) | Optional |
| `REDDIT_CLIENT_SECRET` | Same as above | Optional |

## Sources

| Source | Tool | What it fetches |
|--------|------|-----------------|
| **Web Search** | Tavily API | Breaking AI/tech news |
| **RSS** | feedparser | TechCrunch, Ars Technica, The Verge |
| **GitHub** | Scraping | Daily trending repositories |
| **Reddit** | OAuth API | r/MachineLearning, r/artificial, r/LocalLLaMA |

## Architecture

Built on the same stack as [deep-research](https://github.com/ShonP/deep-research):

- **Microsoft Agent Framework (MAF) 1.2.0** — agents, tools, middleware
- **Azure OpenAI** — gpt-5.5 for scanning, scoring, and writing
- **Pydantic v2** — models and settings
- **Structured logging** — colored console + token tracking

### Agents

| Agent | Role | File |
|-------|------|------|
| **Scanner** | Searches all sources, collects raw articles | `newsroom/agents/scanner.py` |
| **Editor** | Scores relevance, deduplicates, selects top stories | `newsroom/agents/editor.py` |
| **Writer** | Formats curated articles into a readable digest | `newsroom/agents/writer.py` |

### Project Structure

```
newsroom/
  config.py           # Settings via pydantic-settings (.env)
  client.py           # Azure OpenAI client factory
  log.py              # Colored structured logging
  middleware.py        # LLM call logging + token tracking
  pipeline.py         # Orchestrator: scan → curate → write
  cli.py              # Click CLI
  models/
    article.py        # Article, ScoredArticle, NewsDigest (Pydantic)
  agents/
    scanner.py        # Source scanning agent
    editor.py         # Scoring & curation agent
    writer.py         # Digest formatting agent
  tools/
    web_search.py     # Tavily search (@tool)
    rss.py            # RSS/Atom feed parser (@tool)
    github_trending.py # GitHub trending scraper (@tool)
    reddit.py         # Reddit API (@tool)
```

## OpenClaw Integration

Run as a cron job to auto-deliver digests to Telegram/Discord:

```bash
# Add cron job (every 8 hours)
openclaw cron add --schedule "0 */8 * * *" \
  --command "cd ~/projects/newsroom && uv run newsroom digest" \
  --delivery telegram:-1003730327593:topic:21
```

## Cost

~$0.25 per digest run (~48K tokens on gpt-5.5).

## License

MIT
