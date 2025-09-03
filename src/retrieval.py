from typing import List, Dict, Any, Optional
from datetime import datetime

from src.indexer import mail_indexer


def retrieve_citations(query_terms: List[str], sender: Optional[str] = None, top_k: int = 10) -> List[Dict[str, Any]]:
    """Simple lexical+recency retrieval over the SQLite index returning citations.
    This is a first pass; can be upgraded with embeddings when enabled.
    """
    seen_ids = set()
    results: List[Dict[str, Any]] = []
    for term in query_terms:
        cand = mail_indexer.search_lexical(term, sender=sender, top_k=top_k)
        for c in cand:
            if c["id"] in seen_ids:
                continue
            seen_ids.add(c["id"])
            results.append({
                "id": c["id"],
                "sender": c.get("sender", ""),
                "subject": c.get("subject", ""),
                "bodyPreview": c.get("body_preview", ""),
                "receivedDateTime": c.get("received_utc", ""),
            })
            if len(results) >= top_k:
                break
        if len(results) >= top_k:
            break
    return results


