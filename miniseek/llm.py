import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

class LLMProvider:
    """Abstract base provider for local model inference backends."""
    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

class OllamaProvider(LLMProvider):
    """Ollama local inference provider using Python standard library (urllib)."""
    
    def __init__(self, model_name: str = "qwen2.5:1.5b", host: str = "http://127.0.0.1:11434"):
        self.model_name = model_name
        self.host = host.rstrip("/")

    def chat(self, messages: List[Dict[str, str]], system: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends a chat request to Ollama HTTP API endpoint (/api/chat).
        
        Request Payload structure:
        {
            "model": "qwen2.5:1.5b",
            "messages": [{"role": "user", "content": "..."}],
            "stream": false
        }
        """
        url = f"{self.host}/api/chat"
        
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)

        payload = {
            "model": self.model_name,
            "messages": payload_messages,
            "stream": False,
            "format": "json"
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
                res_json = json.loads(body)
                return {
                    "content": res_json.get("message", {}).get("content", ""),
                    "model": res_json.get("model"),
                    "total_duration_ms": res_json.get("total_duration", 0) // 1_000_000,
                    "eval_count": res_json.get("eval_count", 0),
                    "eval_duration_ms": res_json.get("eval_duration", 0) // 1_000_000
                }
        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to communicate with Ollama at {self.host}. Is `ollama serve` running? Error: {e}")
