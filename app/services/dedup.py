"""Semantic deduplication using sentence embeddings."""

from datetime import datetime, timedelta, timezone
from threading import Lock

import numpy as np
from sqlalchemy import update

from app.models import News
from app.services.feed_parser import utc_iso

_embedding_model = None
_embedding_lock = Lock()


def get_embedding_model():
    """Lazily load the sentence-transformer model (thread-safe)."""
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                from sentence_transformers import SentenceTransformer
                _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def mark_new_duplicates(session, threshold):
    """Compute embeddings for new items and mark semantic duplicates.

    Args:
        session: SQLAlchemy session
        threshold: Cosine similarity threshold (0.0-1.0)
    """
    new_rows = session.query(News.id, News.title).filter(
        News.embedding.is_(None)
    ).all()
    if not new_rows:
        return

    model = get_embedding_model()
    new_titles = [r.title for r in new_rows]
    new_ids = [r.id for r in new_rows]
    new_embeddings = model.encode(new_titles, normalize_embeddings=True)

    # Load recent existing embeddings for comparison (last 48h)
    cutoff = utc_iso(datetime.now(timezone.utc) - timedelta(hours=48))
    existing_rows = session.query(News.id, News.embedding).filter(
        News.embedding.isnot(None),
        News.fetched_at >= cutoff,
    ).all()

    existing_embeddings = None
    if existing_rows:
        existing_embeddings = np.array([
            np.frombuffer(r.embedding, dtype=np.float32) for r in existing_rows
        ])

    for i in range(len(new_ids)):
        emb = new_embeddings[i]
        is_dup = False

        # Check against existing items
        if existing_embeddings is not None and len(existing_embeddings) > 0:
            sims = existing_embeddings @ emb
            if float(np.max(sims)) >= threshold:
                is_dup = True

        # Check against earlier items in the same batch
        if not is_dup and i > 0:
            batch_sims = new_embeddings[:i] @ emb
            if float(np.max(batch_sims)) >= threshold:
                is_dup = True

        session.execute(
            update(News).where(News.id == new_ids[i]).values(
                embedding=emb.tobytes(),
                duplicate=1 if is_dup else 0,
            )
        )

    session.commit()
