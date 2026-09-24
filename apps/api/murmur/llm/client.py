"""Streaming client for a local Ollama model."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_HOST = "http://127.0.0.1:11434"


class Ollama:
    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST) -> None:
        self.model = model
        self.host = host

    def stream(
        self,
        system: str,
        user: str,
        timeout: float = 120.0,
        num_predict: int = 220,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Yield reply text chunks. Thinking is disabled: it costs seconds of
        latency and Murmur only needs the spoken answer. The budget allows for
        the trailing affect block as well as the reply itself."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
            "think": False,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        with httpx.stream(
            "POST", f"{self.host}/api/chat", json=payload, timeout=timeout
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                chunk = event.get("message", {}).get("content", "")
                if chunk:
                    yield chunk
                if event.get("done"):
                    return
