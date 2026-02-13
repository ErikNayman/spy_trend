"""
llm_explain.py – Optional LLM explanation via Anthropic API.

Requires ANTHROPIC_API_KEY environment variable to be set.
Falls back gracefully if missing or if the API call fails.
"""
import json
import os

import requests


def explain_with_llm(context: dict, mode: str = "concise") -> str:
    """Call Anthropic API for plain-English explanation. Returns markdown.

    Args:
        context: Dict with winner name, params, metrics, constraints.
        mode: "concise" (default) or "detailed".

    Returns:
        Markdown explanation string, or empty string if API is unavailable.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    system_prompt = (
        "You are a quantitative research assistant explaining backtest results "
        "to a non-technical audience. Use ONLY the provided numbers. "
        "Do not invent results or metrics not in the data. "
        "Not financial advice. Keep it under 200 words."
    )

    if mode == "detailed":
        user_prompt = (
            "Explain the following strategy selection result in detail. "
            "Cover: what the strategy does, why it was selected, key risks, "
            "and what the numbers mean.\n\n"
            f"```json\n{json.dumps(context, indent=2, default=str)}\n```"
        )
    else:
        user_prompt = (
            "Give a concise plain-English summary of this strategy selection. "
            "Focus on: what was chosen, why, and the key risk/return tradeoff.\n\n"
            f"```json\n{json.dumps(context, indent=2, default=str)}\n```"
        )

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-5-20250929",
                "max_tokens": 512,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
    except Exception:
        return ""
