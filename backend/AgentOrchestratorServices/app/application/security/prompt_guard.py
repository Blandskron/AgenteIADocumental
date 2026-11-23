"""Prompt-injection detection & delimiter neutralization for documentary snippets (AG-036)."""

from __future__ import annotations

import re

INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignore_instructions", re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE)),
    ("system_role_spoof", re.compile(r"(^|\n)\s*(system|assistant)\s*:", re.IGNORECASE)),
    ("delimiter_break", re.compile(r"</?\s*(document_context|conversation_history|user_question)\s*>", re.IGNORECASE)),
    ("special_token_spoof", re.compile(r"<\|(im_start|im_end|system|endoftext)\|>", re.IGNORECASE)),
    ("exfiltrate_secret", re.compile(r"(reveal|print|dump|show)\s+(your\s+)?(system\s+prompt|api[_\s]?key|jwt|token)", re.IGNORECASE)),
)


def detect_prompt_injection_patterns(text: str) -> list[str]:
    """Returns names of any prompt-injection patterns detected in untrusted text."""
    content = text or ""
    found: list[str] = []
    for name, pattern in INJECTION_PATTERNS:
        if pattern.search(content):
            found.append(name)
    return found


def neutralize_document_snippet(snippet: str) -> str:
    """Neutralizes XML delimiter breakout tags and special LLM tokens inside retrieved chunks."""
    cleaned = (snippet or "").replace("\x00", "")
    cleaned = re.sub(
        r"</?\s*(document_context|conversation_history|user_question)\s*>",
        "[tag_neutralizado]",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"<\|(im_start|im_end|system|endoftext)\|>", "[token_neutralizado]", cleaned, flags=re.IGNORECASE)
    return cleaned


def sanitize_user_goal(goal: str) -> str:
    """Normalizes user goal text and strips null bytes or delimiter breakout attempts."""
    cleaned = (goal or "").replace("\x00", "").strip()
    cleaned = re.sub(
        r"</?\s*(document_context|conversation_history|user_question)\s*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"<\|(im_start|im_end|system|endoftext)\|>", "", cleaned, flags=re.IGNORECASE)
    return cleaned[:4000]
