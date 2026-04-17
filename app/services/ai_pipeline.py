"""Global AI-analysis queue — consumes new article IDs asynchronously.

Single process-wide long-lived `ThreadPoolExecutor` so pollers never block on
Bedrock. Producers call `enqueue_for_analysis([ids...])`; a dispatcher thread
batches IDs into Bedrock calls at a steady cadence.
"""

from __future__ import annotations

import logging
import threading
import time
from queue import Queue, Empty
from typing import List, Optional

from app.services.metrics import emit_metric

logger = logging.getLogger("signal.ai_pipeline")

_AI_NAMESPACE = "InstantNews/AIPipeline"
# Rate-limit QueueDepth emission so hot-loop iterations don't flood logs.
_QUEUE_DEPTH_MIN_INTERVAL_SECONDS = 5.0

_queue: "Queue[int]" = Queue()
_dispatcher_thread: Optional[threading.Thread] = None
_dispatcher_lock = threading.Lock()
_stop_event = threading.Event()
_session_factory_ref = None


def enqueue_for_analysis(article_ids: List[int]) -> None:
    for aid in article_ids:
        _queue.put(aid)


def _dispatcher_loop(session_factory, batch_size: int = 25, batch_window_seconds: float = 1.5) -> None:
    """Drain the queue into batches, run AI analysis, then drain again.

    Each batch runs to completion in a worker thread (spawned per batch) so the
    dispatcher can immediately start gathering the next batch. Keeps the queue
    moving even if one batch is slow.
    """
    from app.services.feed_refresh import _run_bedrock_analysis
    logger.info("ai_pipeline dispatcher started batch_size=%d window=%.1fs",
                batch_size, batch_window_seconds)
    last_queue_depth_emit = 0.0
    while not _stop_event.is_set():
        # Emit the QueueDepth gauge at most once every few seconds regardless
        # of how often the outer loop iterates (default batch_window_seconds
        # is 1.5s, but operators may tune it lower — protect against log spam).
        now_mono = time.monotonic()
        if now_mono - last_queue_depth_emit >= _QUEUE_DEPTH_MIN_INTERVAL_SECONDS:
            emit_metric(
                namespace=_AI_NAMESPACE,
                metric_name="QueueDepth",
                value=_queue.qsize(),
                unit="Count",
                dimensions=None,
            )
            last_queue_depth_emit = now_mono

        batch: List[int] = []
        try:
            # Block up to batch_window_seconds for the first id
            first = _queue.get(timeout=batch_window_seconds)
            batch.append(first)
        except Empty:
            continue
        # Drain up to batch_size more without blocking
        deadline = time.monotonic() + batch_window_seconds
        while len(batch) < batch_size and time.monotonic() < deadline:
            try:
                batch.append(_queue.get_nowait())
            except Empty:
                break
        # Fire batch in its own daemon thread so dispatcher isn't blocked
        t = threading.Thread(
            target=_run_bedrock_analysis,
            args=(session_factory, batch),
            daemon=True,
            name=f"ai-batch-{len(batch)}",
        )
        t.start()
    logger.info("ai_pipeline dispatcher stopped")


def ensure_started(session_factory) -> None:
    """Idempotently start the dispatcher. Safe to call from multiple pollers."""
    global _dispatcher_thread, _session_factory_ref
    with _dispatcher_lock:
        if _dispatcher_thread and _dispatcher_thread.is_alive():
            return
        _session_factory_ref = session_factory
        _stop_event.clear()
        _dispatcher_thread = threading.Thread(
            target=_dispatcher_loop,
            args=(session_factory,),
            daemon=True,
            name="ai-pipeline-dispatcher",
        )
        _dispatcher_thread.start()


def stop() -> None:
    _stop_event.set()
