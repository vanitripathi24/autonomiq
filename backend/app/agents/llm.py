"""Thin LLM client (Gemini or OpenAI over REST). Every caller has a rules-based fallback."""
import json
import re
import httpx
from .. import config


def available() -> bool:
    return bool(config.GEMINI_API_KEY or config.OPENAI_API_KEY)


def provider() -> str:
    if config.GEMINI_API_KEY:
        return f"Gemini ({config.GEMINI_MODEL})"
    if config.OPENAI_API_KEY:
        return f"OpenAI ({config.OPENAI_MODEL})"
    return "Rules engine"


def complete(system: str, prompt: str, json_mode: bool = False, timeout: float = 25) -> str | None:
    try:
        if config.GEMINI_API_KEY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
            body = {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.4, **({"responseMimeType": "application/json"} if json_mode else {})},
            }
            r = httpx.post(url, params={"key": config.GEMINI_API_KEY}, json=body, timeout=timeout)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        if config.OPENAI_API_KEY:
            body = {
                "model": config.OPENAI_MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "temperature": 0.4,
                **({"response_format": {"type": "json_object"}} if json_mode else {}),
            }
            r = httpx.post("https://api.openai.com/v1/chat/completions", json=body, timeout=timeout,
                           headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None
    return None


def complete_json(system: str, prompt: str) -> dict | None:
    text = complete(system, prompt, json_mode=True)
    if not text:
        return None
    try:
        return json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip())
    except Exception:
        return None
