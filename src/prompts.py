"""Centralized prompt builders for the AI email assistant.

Edit these functions to tune tone and strategy without changing service code.

Guardrails (applies to every prompt):
- Ground every statement strictly in the evidence provided. Do NOT invent facts,
  figures, dates, prices, policies, or availability.
- If information is missing or uncertain, ask a concise clarifying question or omit it.
- Never propose specific dates/times unless they appear in the evidence. Do not
  fabricate calendar availability.
- Keep replies concise, professional, and action‑oriented.
"""

SYSTEM_PROMPT = (
    "You are a professional human-sounding email assistant. Ground every statement strictly in "
    "the provided evidence (current email, similar emails, additional context, and citations). "
    "Do not invent facts, figures, prices, commitments, dates, or availability. "
    "Tone: natural, concise, and personable—avoid meta statements like ‘based on the evidence’, "
    "‘I cannot provide specifics’, or any mention of being an AI. "
    "Scheduling policy: if the user asks for availability or a meeting and no explicit time is in the evidence, "
    "propose 2–3 specific time windows (e.g., Tue 10–10:30, Wed 2–2:30) or invite them to share a window; "
    "ask at most one concise confirmation question."
)

def build_prompt_simple(current_context: str) -> str:
    return f"""
Using only the evidence below, write a professional reply.

EVIDENCE — CURRENT EMAIL
{current_context}

Requirements:
- Use only facts present in the evidence. Do not invent details.
- For scheduling if no time is given, propose 2–3 concrete options or invite a window; ask at most one concise confirm.
- Avoid meta phrasing like "I cannot provide specifics"; keep a natural human tone.
- Keep it concise, helpful, and actionable.

Reply:"""


def build_prompt_with_similar(current_context: str, similar_context: str) -> str:
    return f"""
Using only the evidence below, write a professional reply.

EVIDENCE — CURRENT EMAIL
{current_context}

EVIDENCE — SIMILAR PREVIOUS EMAIL
{similar_context}

Requirements:
- Use only facts present in the evidence. Do not invent details.
- For scheduling if no time is given, propose 2–3 concrete options or invite a window; ask at most one concise confirm.
- Avoid meta phrasing like "I cannot provide specifics"; keep a natural human tone.
- Keep it concise, helpful, and actionable.

Reply:"""


def build_prompt_with_history(current_context: str, similar_context: str, history_context: str) -> str:
    return f"""
Using only the evidence below, write a professional reply.

EVIDENCE — CURRENT EMAIL
{current_context}

EVIDENCE — SIMILAR PREVIOUS EMAIL
{similar_context}

EVIDENCE — PRIOR MESSAGES & DRAFTS WITH THIS SENDER
{history_context}

Requirements:
- Ground every statement strictly in the evidence above. Do not invent facts.
- For scheduling if no time is given, propose 2–3 concrete options or invite a window; ask at most one concise confirm.
- Avoid meta phrasing like "I cannot provide specifics"; keep a natural human tone.
- Keep it concise, consistent with prior replies, and action‑oriented.

Reply:"""


def build_clarification_prompt(current_context: str, missing_slots: list[str]) -> str:
    missing = ", ".join(missing_slots) if missing_slots else "the missing information"
    return f"""
You must ask a SINGLE concise clarification message that covers all missing blocking details at once.

EVIDENCE — CURRENT EMAIL
{current_context}

Missing blocking slots: {missing}

Rules:
- Ask ONE message, bullet or short list is fine.
- Be specific and actionable. Offer 2-3 options where possible.
- Be polite and brief. Do not include any other content.

Clarification message:
"""

