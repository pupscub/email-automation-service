import re
from typing import Dict


SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _normalize(text: str) -> str:
    return (text or "").lower()


def _tokens_of_interest(text: str) -> set:
    """Extract tokens that are likely to be risky if hallucinated.

    - dates/months/weekdays
    - time formats (e.g., 3:30, 3pm)
    - currency amounts or numbers with symbols
    - explicit urls/emails
    """
    t = _normalize(text)
    tokens = set()
    # months and weekdays
    for w in [
        "january","february","march","april","may","june","july","august","september","october","november","december",
        "mon","tue","tues","weds","wed","thu","thur","thurs","fri","sat","sun",
        "monday","tuesday","wednesday","thursday","friday","saturday","sunday"
    ]:
        if w in t:
            tokens.add(w)
    # time patterns
    for m in re.findall(r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\s?(am|pm)\b", t):
        if isinstance(m, tuple):
            tokens.add(" ".join(m).strip())
        else:
            tokens.add(m)
    # currency and numbers
    for m in re.findall(r"\$\d+[\d,]*(\.\d+)?|\b\d+\.\d+\b|\b\d{4}\b", t):
        tokens.add(m)
    # urls/emails
    for m in re.findall(r"https?://\S+|\b[\w\.-]+@[\w\.-]+\b", t):
        tokens.add(m.lower())
    return tokens


def verify_and_filter(draft_html: str, evidence_text: str) -> Dict:
    """Heuristic verifier.

    For each sentence, if it contains high‑risk tokens that do not appear
    anywhere in the evidence, remove that sentence. Returns filtered text
    (still HTML-friendly) and counts.
    """
    # Work on a text version (strip simple tags)
    draft_text = re.sub(r"<[^>]+>", " ", draft_html or "")
    evidence_norm = _normalize(evidence_text)

    sentences = SENTENCE_SPLIT.split(draft_text.strip()) if draft_text.strip() else []
    kept = []
    removed = []
    for s in sentences:
        toks = _tokens_of_interest(s)
        if not toks:
            kept.append(s)
            continue
        # if any risky token not in evidence, remove
        unsupported = [tok for tok in toks if tok not in evidence_norm]
        if unsupported:
            removed.append(s)
        else:
            kept.append(s)

    filtered_text = " ".join(kept).strip()
    return {
        "filtered_text": filtered_text if filtered_text else draft_text,
        "removed_count": len(removed),
        "removed_sentences": removed,
    }


