# PRD: First-Hand Source Acquisition Pipeline

## 1. Introduction/Overview

InstantNews currently aggregates 16 RSS feeds from secondary media (CNBC, Reuters, MarketWatch, etc.) using a synchronous polling worker. This PRD defines a **first-hand source acquisition pipeline** that bypasses media intermediaries to collect signals directly from primary sources — government agencies (SEC EDGAR, Federal Reserve, Treasury), corporate IR webcasts, press wire services, and live broadcast transcription.

The pipeline introduces four new infrastructure layers to the existing Flask + ECS architecture:

1. **Source Discovery** — Playwright headless browser + RSS/API monitors to find live streams and detect new filings
2. **Audio Capture** — ffmpeg pipe-based HLS stream capture for live broadcasts
3. **ASR Transcription** — Deepgram Nova-2 streaming for real-time speech-to-text
4. **Signal Extraction** — LLM-powered structured signal generation (extending existing `bedrock_analysis.py` patterns)

Plus a new **Redis Streams event bus** for real-time signal delivery via WebSocket/SSE, replacing the current database-polling model.

**Core principle:** Output structured JSON signals only — no raw audio/video/text redistribution — to avoid copyright issues.

**Target latency:** < 7 seconds end-to-end (live event → signal delivered to user).

**Current state of codebase:**
- No Redis, no WebSocket, no streaming infrastructure
- Worker is synchronous polling loop (`app/worker.py`)
- AI analysis uses MiniMax → Claude → Bedrock fallback chain (`app/services/bedrock_analysis.py`)
- Flask app factory pattern (`app/__init__.py`), SQLAlchemy ORM, Alembic migrations
- ECS Fargate deployment with ALB (no sticky sessions, no WebSocket support yet)
- Frontend is vanilla JS with 5-second polling (`frontend/src/terminal-app.js`)

## 2. Goals

- Ingest first-hand text sources (SEC EDGAR, Fed, Treasury, press wires) with < 15s latency
- Discover and capture live HLS streams (C-SPAN, WhiteHouse.gov, Fed YouTube) automatically
- Transcribe live audio to text via Deepgram Nova-2 streaming with < 500ms ASR latency
- Extract structured trading signals from transcripts/text using existing LLM fallback chain
- Deliver signals in real-time via WebSocket/SSE (replacing 5-second polling)
- Cross-source deduplication via Redis Streams event bus
- All new code follows existing patterns: app factory, service modules, structured logging, session-per-request

## 3. User Stories

---

### US-001: Signal Data Model & Migration

**Description:** As a developer, I want a new `Signal` database model so that first-hand source signals are stored separately from RSS news items with richer metadata.

**Acceptance Criteria:**
- [ ] New `Signal` model in `app/models.py` with fields: `id` (UUID), `timestamp`, `source_type` (enum: government/corporate/wire/broadcast/social), `source_name`, `source_url`, `is_first_hand` (bool), `entities` (JSON array), `tickers_affected` (JSON array), `event_type` (enum: rate_decision/earnings/filing/M&A/macro/policy/other), `headline`, `sentiment_score` (float), `sentiment_label`, `impact_score` (float), `novelty` (enum: breaking/update/rehash), `raw_excerpt` (text, max 500 chars), `confidence` (float), `latency_ms` (int), `created_at`
- [ ] Alembic migration creates the `signals` table
- [ ] `alembic upgrade head` runs without error
- [ ] `alembic downgrade -1` cleanly drops the table
- [ ] Typecheck passes (`mypy app/models.py --ignore-missing-imports`)

**Test Strategy:** cli

**Test Assertions:**
- `alembic upgrade head` exits 0
- `python3 -c "from app.models import Signal; print(Signal.__tablename__)"` prints `signals`
- `python3 -c "from app.models import Signal; cols = [c.name for c in Signal.__table__.columns]; assert 'signal_id' not in cols; assert 'source_type' in cols; assert 'tickers_affected' in cols; print('OK')"` exits 0
- `alembic downgrade -1` exits 0
- `mypy app/models.py --ignore-missing-imports` exits 0

---

### US-002: Signal Output Schema & Serializer

**Description:** As a developer, I want a signal serialization module so that all pipeline outputs conform to the defined JSON schema.

**Acceptance Criteria:**
- [ ] New module `app/services/signal_schema.py` with `SignalOutput` dataclass/Pydantic model matching the schema from the PRD (Section 3.2 of original spec)
- [ ] `serialize_signal(signal_model) -> dict` converts a `Signal` ORM instance to API-ready JSON
- [ ] `validate_signal(data: dict) -> bool` validates a dict against the schema
- [ ] Includes `SOURCE_CREDIBILITY_WEIGHTS` dict mapping source types to float weights
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.signal_schema import SignalOutput, serialize_signal, validate_signal; print('imports OK')"` exits 0
- `python3 -c "from app.services.signal_schema import validate_signal; assert validate_signal({'source': {'type': 'government', 'name': 'Fed', 'is_first_hand': True}, 'event_type': 'rate_decision', 'headline': 'test', 'sentiment': {'score': 0.5, 'label': 'neutral'}, 'tickers_affected': ['SPY'], 'impact_score': 5.0, 'novelty': 'breaking', 'confidence': 0.9}); print('valid')"` exits 0
- `python3 -c "from app.services.signal_schema import validate_signal; assert not validate_signal({}); print('rejects empty')"` exits 0
- `mypy app/services/signal_schema.py --ignore-missing-imports` exits 0

---

### US-003: Redis Streams Event Bus

**Description:** As a developer, I want a Redis Streams-based event bus so that signals can be published once and consumed by multiple downstream systems (API, WebSocket, storage).

**Acceptance Criteria:**
- [ ] New module `app/services/event_bus.py` wrapping Redis Streams
- [ ] `publish_signal(signal_dict)` writes to stream `signals:live`
- [ ] `create_consumer_group(group_name)` creates a consumer group on the stream
- [ ] `consume_signals(group_name, consumer_id, count, block_ms)` reads new messages
- [ ] `ack_signal(group_name, message_id)` acknowledges processing
- [ ] Config: `REDIS_URL` env var added to `app/config.py` (default `redis://localhost:6379/0`)
- [ ] Graceful fallback: if Redis unavailable, `publish_signal` logs warning and returns (no crash)
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.event_bus import EventBus; print('import OK')"` exits 0
- `python3 -c "from app.config import Config; assert hasattr(Config, 'REDIS_URL'); print(Config.REDIS_URL)"` exits 0
- `mypy app/services/event_bus.py --ignore-missing-imports` exits 0

---

### US-004: SEC EDGAR RSS Poller

**Description:** As a developer, I want a SEC EDGAR Full-Text RSS feed poller so that new 8-K, 4, and 13F filings are ingested as signals within 15 seconds of publication.

**Acceptance Criteria:**
- [ ] New module `app/services/sources/edgar.py`
- [ ] `EdgarPoller` class with configurable poll interval (default 10s)
- [ ] Parses EDGAR Full-Text RSS feed for filing types: 8-K, 4, 13F
- [ ] Extracts: company name, CIK, filing type, filing URL, filed date
- [ ] Converts each filing to signal dict via `signal_schema.py` and publishes to event bus
- [ ] Tracks last-seen entry ID to avoid reprocessing
- [ ] Structured logging under `signal.sources.edgar` logger
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.sources.edgar import EdgarPoller; print('import OK')"` exits 0
- `python3 -c "from app.services.sources.edgar import EdgarPoller; p = EdgarPoller(); assert p.poll_interval == 10; print('default interval OK')"` exits 0
- `mypy app/services/sources/edgar.py --ignore-missing-imports` exits 0

---

### US-005: Federal Reserve & Treasury Page Monitor

**Description:** As a developer, I want a page-change monitor for federalreserve.gov and treasury.gov so that FOMC statements and Treasury announcements are detected within seconds.

**Acceptance Criteria:**
- [ ] New module `app/services/sources/gov_monitor.py`
- [ ] `PageMonitor` class that polls configured URLs and detects content changes via SHA-256 hash comparison
- [ ] Supports configurable poll intervals per URL (default 30s, FOMC day override to 1s)
- [ ] Fed URLs: FOMC calendar page, press releases page
- [ ] Treasury URLs: auction results page, sanctions/OFAC announcements page
- [ ] On change detection: extracts new content diff, sends to LLM signal extraction, publishes signal
- [ ] Structured logging under `signal.sources.gov` logger
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.sources.gov_monitor import PageMonitor; print('import OK')"` exits 0
- `python3 -c "from app.services.sources.gov_monitor import PageMonitor; m = PageMonitor('https://example.com', interval=5); assert m.interval == 5; print('OK')"` exits 0
- `mypy app/services/sources/gov_monitor.py --ignore-missing-imports` exits 0

---

### US-006: Press Wire RSS Poller (GlobeNewswire / PR Newswire / BusinessWire)

**Description:** As a developer, I want RSS pollers for major press wire services so that corporate announcements (earnings, M&A, management changes) are ingested as signals.

**Acceptance Criteria:**
- [ ] New module `app/services/sources/press_wires.py`
- [ ] `PressWirePoller` class supporting multiple RSS feed URLs
- [ ] Preconfigured feeds: GlobeNewswire, PR Newswire, BusinessWire RSS endpoints
- [ ] Poll interval: 15 seconds
- [ ] Each item parsed into signal dict: extracts company name, ticker (from title/body), event type classification
- [ ] Dedup against recent signals (by headline similarity within 60s window)
- [ ] Structured logging under `signal.sources.wires` logger
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.sources.press_wires import PressWirePoller; print('import OK')"` exits 0
- `python3 -c "from app.services.sources.press_wires import PressWirePoller; p = PressWirePoller(); assert len(p.feed_urls) >= 3; print('feeds configured')"` exits 0
- `mypy app/services/sources/press_wires.py --ignore-missing-imports` exits 0

---

### US-007: LLM Signal Extractor

**Description:** As a developer, I want a signal extraction service that takes raw text (transcripts, filings, press releases) and outputs structured trading signals using the existing LLM fallback chain.

**Acceptance Criteria:**
- [ ] New module `app/services/signal_extractor.py`
- [ ] `extract_signal(text, source_metadata) -> SignalOutput` function
- [ ] Uses existing fallback chain pattern from `bedrock_analysis.py`: MiniMax → Claude → Bedrock
- [ ] System prompt instructs LLM to extract: entities, tickers_affected, event_type, headline, sentiment, novelty assessment
- [ ] Supports ticker fuzzy matching ("the iPhone maker" → AAPL) via a configurable alias map
- [ ] Impact score calculation: `source_credibility × sentiment_intensity × category_weight × ticker_liquidity`
- [ ] Low-confidence results (< 0.7) escalated to stronger model (Claude Sonnet) for re-extraction
- [ ] Prompt and model config added to `bedrock_config.py`
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.signal_extractor import extract_signal; print('import OK')"` exits 0
- `python3 -c "from app.services.bedrock_config import SIGNAL_EXTRACTION_PROMPT; assert len(SIGNAL_EXTRACTION_PROMPT) > 100; print('prompt configured')"` exits 0
- `mypy app/services/signal_extractor.py --ignore-missing-imports` exits 0

---

### US-008: Playwright Stream Discovery Service

**Description:** As a developer, I want a Playwright-based service that automatically discovers HLS `.m3u8` stream URLs from preconfigured live broadcast pages.

**Acceptance Criteria:**
- [ ] New module `app/services/sources/stream_discovery.py`
- [ ] `StreamDiscovery` class with preconfigured source list: C-SPAN, WhiteHouse.gov/live, Fed YouTube channel
- [ ] Uses Playwright headless Chromium to navigate to pages and intercept network requests containing `.m3u8`
- [ ] For YouTube: uses `yt-dlp --get-url` to extract direct stream URL
- [ ] `discover_streams() -> list[dict]` returns `[{source_name, stream_url, discovered_at}]`
- [ ] `check_live_status(source_name) -> bool` checks if a preconfigured source is currently live
- [ ] Handles page timeouts (10s) and empty results gracefully
- [ ] Structured logging under `signal.sources.streams` logger
- [ ] Typecheck passes

**Test Strategy:** cli

**Test Assertions:**
- `python3 -c "from app.services.sources.stream_discovery import StreamDiscovery; print('import OK')"` exits 0
- `python3 -c "from app.services.sources.stream_discovery import StreamDiscovery; sd = StreamDiscovery(); assert len(sd.sources) >= 3; print('sources configured')"` exits 0
- `mypy app/services/sources/stream_discovery.py --ignore-missing-imports` exits 0

---

### US-009: ffmpeg Audio Capture Manager

**Description:** As a developer, I want an audio capture manager that spawns and monitors ffmpeg processes to extract audio from HLS streams as raw PCM pipe output.

**Acceptance Criteria:**
- [ ] New module `app/services/audio_capture.py`
- [ ] `AudioCapture` class managing multiple concurrent ffmpeg subprocesses
- [ ] `start_capture(stream_url, source_name) -> stream_id` starts an ffmpeg process: `ffmpeg -i <url> -vn -acodec pcm_s16le -ar 16000 -ac 1 -f wav pipe:1`
- [ ] `stop_capture(stream_id)` gracefully terminates the ffmpeg process
- [ ] `get_audio_pipe(stream_id) -> IO` returns the stdout pipe for ASR consumption
- [ ] Supports ≥ 10 concurrent captures
- [ ] Watchdog: detects ffmpeg process exit and auto-restarts with backoff (max 3 retries)
- [ ] `list_active() -> list[dict]` returns active captures with uptime and byte count
- [ ] No disk I/O — all audio piped through memory
- [ ] Structured logging under `signal.capture` logger
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.audio_capture import AudioCapture; print('import OK')"` exits 0
- `python3 -c "from app.services.audio_capture import AudioCapture; ac = AudioCapture(); assert ac.max_concurrent >= 10; print('OK')"` exits 0
- `mypy app/services/audio_capture.py --ignore-missing-imports` exits 0

---

### US-010: Deepgram ASR Streaming Client

**Description:** As a developer, I want a Deepgram Nova-2 streaming ASR client that reads from an audio pipe and emits transcript text chunks in real-time.

**Acceptance Criteria:**
- [ ] New module `app/services/asr_client.py`
- [ ] `DeepgramASR` class wrapping Deepgram Python SDK streaming API
- [ ] `start_transcription(audio_pipe, callback)` reads audio chunks and invokes `callback(text, is_final, speaker_id)` on each result
- [ ] Configured for: Nova-2 model, interim results enabled, speaker diarization enabled, 16kHz sample rate
- [ ] `DEEPGRAM_API_KEY` env var added to `app/config.py`
- [ ] Fallback: if Deepgram unavailable, logs error and sets a flag for callers to check
- [ ] Latency metric: tracks and logs per-utterance ASR latency
- [ ] Structured logging under `signal.asr` logger
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.asr_client import DeepgramASR; print('import OK')"` exits 0
- `python3 -c "from app.config import Config; assert hasattr(Config, 'DEEPGRAM_API_KEY'); print('config OK')"` exits 0
- `mypy app/services/asr_client.py --ignore-missing-imports` exits 0

---

### US-011: Live Broadcast Pipeline Orchestrator

**Description:** As a developer, I want an orchestrator that wires together stream discovery → audio capture → ASR → signal extraction into a managed pipeline per live source.

**Acceptance Criteria:**
- [ ] New module `app/services/broadcast_pipeline.py`
- [ ] `BroadcastPipeline` class that manages the full chain: `StreamDiscovery` → `AudioCapture` → `DeepgramASR` → `signal_extractor` → `EventBus`
- [ ] `start_pipeline(source_name)` discovers stream, starts capture, starts ASR, routes transcript chunks to signal extractor
- [ ] `stop_pipeline(source_name)` cleanly shuts down all stages
- [ ] `status() -> dict` returns per-source status: {source, stage, uptime, signals_emitted, last_signal_at}
- [ ] Handles partial failures: if ASR fails, stops capture; if capture fails, retries stream discovery
- [ ] Accumulates transcript text in buffer, sends to LLM every complete sentence (period/question mark detection)
- [ ] Structured logging under `signal.pipeline` logger
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.broadcast_pipeline import BroadcastPipeline; print('import OK')"` exits 0
- `python3 -c "from app.services.broadcast_pipeline import BroadcastPipeline; bp = BroadcastPipeline(); assert hasattr(bp, 'start_pipeline'); assert hasattr(bp, 'stop_pipeline'); assert hasattr(bp, 'status'); print('API OK')"` exits 0
- `mypy app/services/broadcast_pipeline.py --ignore-missing-imports` exits 0

---

### US-012: Signal Worker Process

**Description:** As a developer, I want a new signal worker process that runs all source pollers, the broadcast pipeline, and event bus consumers as a single managed service.

**Acceptance Criteria:**
- [ ] New module `app/signal_worker.py` (parallel to existing `app/worker.py`)
- [ ] Starts all text source pollers: `EdgarPoller`, `PageMonitor` (Fed, Treasury), `PressWirePoller`
- [ ] Starts `BroadcastPipeline` for configured live sources
- [ ] Starts event bus consumers: one that persists signals to DB, one that feeds WebSocket broadcaster
- [ ] Signal-aware shutdown (SIGTERM/SIGINT): gracefully stops all pollers, pipelines, consumers
- [ ] Health check endpoint or file for container orchestration
- [ ] Runnable via `python -m app.signal_worker`
- [ ] Structured logging under `signal.worker` logger
- [ ] Typecheck passes

**Test Strategy:** cli

**Test Assertions:**
- `python3 -c "from app.signal_worker import main; print('import OK')"` exits 0
- `timeout 3 python -m app.signal_worker --dry-run 2>&1 || true` exits without crash and prints startup log
- `mypy app/signal_worker.py --ignore-missing-imports` exits 0

---

### US-013: WebSocket Signal Delivery Endpoint

**Description:** As a user, I want to receive real-time signal updates via WebSocket so that I don't have to poll the API.

**Acceptance Criteria:**
- [ ] Add `flask-sock` or `python-socketio` dependency to `requirements.txt`
- [ ] New route `WS /api/signals/stream` in `app/routes/signals.py`
- [ ] Authenticates via query param `token` (Firebase JWT) or `api_key`
- [ ] Tier gating: Free users get `headline` + `event_type` only; Pro gets full signal minus `impact_score`; Max gets everything
- [ ] Consumes from Redis Streams consumer group `ws-broadcast`
- [ ] Sends JSON signal messages to all connected clients
- [ ] Handles client disconnect gracefully
- [ ] Structured logging under `signal.ws` logger
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.routes.signals import signals_bp; print('blueprint OK')"` exits 0
- `grep -q 'signals/stream' app/routes/signals.py` exits 0
- `mypy app/routes/signals.py --ignore-missing-imports` exits 0

---

### US-014: REST Signal Query API

**Description:** As a quantitative researcher, I want a REST API to query historical signals with filtering so that I can backtest strategies against first-hand source data.

**Acceptance Criteria:**
- [ ] `GET /api/signals` route in `app/routes/signals.py`
- [ ] Query params: `ticker`, `event_type`, `source_type`, `start_date`, `end_date`, `min_impact`, `novelty`, `limit` (default 50, max 500), `offset`
- [ ] Response includes `total_count` for pagination
- [ ] Tier gating: same field stripping as WebSocket (Free/Pro/Max)
- [ ] Rate limited per tier (reuses existing `rate_limit.py` pattern)
- [ ] Auth via Bearer token or X-API-Key (reuses existing `auth/` middleware)
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.routes.signals import signals_bp; print('blueprint OK')"` exits 0
- `grep -q "GET.*signals" app/routes/signals.py || grep -q "signals.*GET" app/routes/signals.py` exits 0
- `mypy app/routes/signals.py --ignore-missing-imports` exits 0

---

### US-015: Frontend Real-Time Signal Panel

**Description:** As a terminal user, I want a real-time signal feed in the SIGNAL terminal that shows first-hand source signals with live updates via WebSocket.

**Acceptance Criteria:**
- [ ] New file `frontend/src/signal-feed.js` with `SignalFeed` class
- [ ] Connects to `WS /api/signals/stream` with Firebase token
- [ ] Displays signals in a scrolling feed: timestamp, source badge (color-coded by source_type), headline, tickers, sentiment, impact score
- [ ] "LIVE" indicator when WebSocket connected, "RECONNECTING" on disconnect with auto-retry (exponential backoff)
- [ ] Tier-appropriate display: Free users see upgrade prompt for locked fields
- [ ] Integrates into existing terminal layout as a new tab or split panel
- [ ] Follows existing styles in `frontend/src/styles/terminal.css`
- [ ] **Verify in browser:** signal panel renders, WebSocket connects, signals appear
- [ ] Typecheck passes (no JS typecheck, verify in browser instead)

**Test Strategy:** browser

**Test Assertions:**
- File `frontend/src/signal-feed.js` exists
- `grep -q 'WebSocket' frontend/src/signal-feed.js` exits 0
- `grep -q 'signals/stream' frontend/src/signal-feed.js` exits 0
- `cd frontend && npx vite build` exits 0

---

### US-016: Cross-Source Deduplication on Event Bus

**Description:** As a developer, I want cross-source signal deduplication so that the same event reported by multiple sources produces one consolidated signal.

**Acceptance Criteria:**
- [ ] New module `app/services/signal_dedup.py`
- [ ] `is_duplicate(new_signal, window_seconds=60) -> (bool, optional_parent_id)` checks against recent signals in Redis
- [ ] Matching criteria: same `event_type` + overlapping `tickers_affected` + cosine similarity of `headline` > 0.8
- [ ] If duplicate: merges (updates parent signal's confidence, adds source to multi-source list) instead of creating new
- [ ] If novel but related (similarity 0.5-0.8): marks as `novelty: "update"` with reference to parent
- [ ] Reuses embedding approach from existing `app/services/dedup.py` where applicable
- [ ] Typecheck passes

**Test Strategy:** function

**Test Assertions:**
- `python3 -c "from app.services.signal_dedup import is_duplicate; print('import OK')"` exits 0
- `mypy app/services/signal_dedup.py --ignore-missing-imports` exits 0

---

### US-017: Signal Worker ECS Task Definition

**Description:** As a developer, I want the signal worker deployed as a new ECS Fargate task so that it runs alongside the existing web and feed-worker services.

**Acceptance Criteria:**
- [ ] New task definition in `infra/stack.py` for `signal-worker` service
- [ ] Container: same ECR image, command override `python -m app.signal_worker`
- [ ] Resources: 1 vCPU, 2GB memory (needs headroom for Playwright + ffmpeg)
- [ ] Environment: inherits all existing secrets + new `REDIS_URL`, `DEEPGRAM_API_KEY`
- [ ] Redis: add ElastiCache Redis instance (single node, `cache.t3.micro`) to CDK stack
- [ ] Security group: signal-worker → Redis, signal-worker → RDS
- [ ] Health check: ECS container health check command
- [ ] `cdk diff` shows expected changes
- [ ] Typecheck passes (CDK synth succeeds)

**Test Strategy:** cli

**Test Assertions:**
- `cd infra && cdk synth 2>&1 | head -5` exits 0
- `grep -q 'signal-worker' infra/stack.py` exits 0
- `grep -q 'ElastiCache\|elasticache\|redis' infra/stack.py` exits 0

---

### US-018: Docker Compose Local Dev Setup

**Description:** As a developer, I want a local Docker Compose setup for the signal pipeline so that I can develop and test the full pipeline locally.

**Acceptance Criteria:**
- [ ] Updated `docker-compose.override.yml` with: Redis service, signal-worker service
- [ ] Redis mapped to localhost:6379
- [ ] Signal worker mounts local code for hot reload
- [ ] Playwright and ffmpeg available in signal-worker container (or separate Dockerfile)
- [ ] `docker compose up` starts web + feed-worker + signal-worker + redis + postgres
- [ ] `.env.example` updated with new env vars: `REDIS_URL`, `DEEPGRAM_API_KEY`
- [ ] Typecheck passes

**Test Strategy:** cli

**Test Assertions:**
- `grep -q 'redis' docker-compose.override.yml` exits 0
- `grep -q 'signal.worker\|signal-worker' docker-compose.override.yml` exits 0
- `grep -q 'REDIS_URL' .env.example` exits 0
- `grep -q 'DEEPGRAM_API_KEY' .env.example` exits 0

---

## 4. Functional Requirements

- FR-1: The system must poll SEC EDGAR RSS at ≤ 10 second intervals and convert filings to structured signals
- FR-2: The system must detect content changes on federalreserve.gov and treasury.gov within 30 seconds (1 second on FOMC days)
- FR-3: The system must poll press wire RSS feeds (GlobeNewswire, PR Newswire, BusinessWire) at ≤ 15 second intervals
- FR-4: The system must discover HLS stream URLs from preconfigured live broadcast pages using headless Playwright
- FR-5: The system must capture audio from HLS streams via ffmpeg subprocess pipes without writing to disk
- FR-6: The system must transcribe live audio using Deepgram Nova-2 streaming with ≤ 500ms latency
- FR-7: The system must extract structured trading signals from text/transcripts using the existing LLM fallback chain
- FR-8: The system must publish all signals to a Redis Streams event bus
- FR-9: The system must deduplicate signals across sources using entity + event_type + headline similarity within a 60-second window
- FR-10: The system must deliver signals to authenticated users via WebSocket with tier-appropriate field gating
- FR-11: The system must provide a REST API for historical signal queries with filtering and pagination
- FR-12: The system must handle ASR/capture failures gracefully with automatic retry and fallback logging
- FR-13: All signals must conform to the defined Signal Output Schema (Section 3.2 of original spec)

## 5. Non-Goals (Out of Scope)

- Raw audio/video storage or playback (signals and excerpts only)
- Custom/self-hosted ASR model (Deepgram managed service only)
- International market sources (US-only for this phase)
- Mobile app (Web + API only)
- Real-time market data distribution (Polygon.io integration is a separate PRD)
- Twitter/X integration (deferred — API cost/reliability concerns, tracked as Phase 3)
- Sling Blue / paid TV stream capture (deferred — legal review needed)
- Local Whisper fallback for ASR (deferred to Phase 2 hardening)
- FastAPI migration (staying on Flask with flask-sock for WebSocket)

## 6. Design Considerations

- Signal feed integrates into existing terminal as a new tab (alongside current RSS news feed)
- Source type badges use color coding: government (red), corporate (blue), wire (green), broadcast (purple)
- Impact score displayed as a 1-10 bar indicator
- "LIVE" indicator pulses when WebSocket is connected
- Existing terminal styles in `frontend/src/styles/terminal.css` extended, not replaced
- Signal detail modal reuses the existing modal pattern from terminal-app.js

## 7. Technical Considerations

- **Flask WebSocket:** Use `flask-sock` (lightweight, works with existing Flask app) rather than `python-socketio` (heavier, ASGI)
- **ALB WebSocket:** AWS ALB supports WebSocket natively — no infra changes needed, but sticky sessions should be enabled for the web service target group
- **Playwright in container:** Needs Chromium dependencies in Docker image — use `playwright install --with-deps chromium` in Dockerfile
- **ffmpeg in container:** Add `ffmpeg` to Dockerfile.prod apt dependencies
- **Redis connection pooling:** Use `redis-py` with connection pool; share pool across event bus, dedup, and cache
- **Sentence embeddings:** Reuse the lazy-loaded model from `app/services/dedup.py` for headline similarity
- **Worker isolation:** Signal worker runs as separate ECS task (not in web container) to avoid memory/CPU contention from Playwright + ffmpeg
- **Graceful shutdown:** All long-running loops must handle SIGTERM for ECS task stops (pattern exists in `app/worker.py`)
- **Database writes:** Signal persistence consumer writes in batches (every 1s or 10 signals, whichever first) to avoid per-signal DB round trips

## 8. Success Metrics

| Metric | MVP Target | 6-Month Target |
|--------|-----------|----------------|
| End-to-end latency (P95) | < 7s | < 5s |
| Signal accuracy (entity + sentiment) | > 85% | > 92% |
| Active first-hand sources | 5+ | 15+ |
| System uptime | 95% | 99.5% |
| Cross-source dedup accuracy | > 90% | > 97% |
| Daily signal volume | 50+ | 500+ |

## 9. Open Questions

- **Deepgram pricing:** At scale (10+ concurrent streams during earnings season), ASR costs could spike. Should we implement a priority queue that only transcribes highest-value streams?
- **FOMC day scaling:** The 1-second Fed page poll interval generates significant load. Should we use a separate lightweight poller or a CloudWatch Events trigger?
- **Signal retention:** How long to keep signals in PostgreSQL before archiving to S3? 1 year? Match the existing `MAX_AGE_DAYS` config?
- **WebSocket scaling:** With ECS auto-scaling, WebSocket connections will be lost on task replacement. Should we implement reconnection state (last-seen signal ID) from the start?
- **Playwright resource usage:** Headless Chromium is memory-hungry (~200MB per page). With 5+ sources, the signal worker needs 2GB+. Should stream discovery run on a schedule (every 5 min) rather than continuously?
