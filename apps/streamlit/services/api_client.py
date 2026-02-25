import hashlib
import random
import time
from datetime import datetime

import requests


class APIClient:
    def __init__(self, state):
        self.state = state

    def _now(self):
        return datetime.utcnow().isoformat() + "Z"

    def create_runtime_token(self):
        key = str(self.state["api_config"].get("api_key", "")).strip()
        if not key:
            return "runtime-anon"
        digest = hashlib.sha256(f"{key}:{time.time()}".encode("utf-8")).hexdigest()
        return f"runtime-{digest[:12]}"

    def _mask_token(self, token):
        if not token or token == "runtime-anon":
            return token or "runtime-anon"
        if len(token) < 8:
            return "runtime-***"
        return f"{token[:10]}***"

    def _parse_endpoint(self, endpoint):
        parts = endpoint.strip().split(" ", 1)
        if len(parts) == 1:
            return "POST", parts[0]
        return parts[0].upper(), parts[1]

    def _append_log(self, endpoint, payload, mode, error=""):
        entry = {
            "id": f"log-{int(time.time() * 1000)}-{random.randint(1000, 999999)}",
            "endpoint": endpoint,
            "payload": payload,
            "at": self._now(),
            "mode": mode,
        }
        if error:
            entry["error"] = error
        logs = self.state.get("api_log", [])
        self.state["api_log"] = [entry] + logs[:24]

    def call(self, endpoint, payload=None):
        payload = payload or {}
        token = payload.get("runtime_token") or self.create_runtime_token()
        payload_with_token = dict(payload)
        payload_with_token["runtime_token"] = token

        safe_payload = dict(payload_with_token)
        safe_payload["runtime_token"] = self._mask_token(token)

        mode = self.state["api_config"].get("mode", "mock")
        provider = self.state["api_config"].get("provider", "openai")
        model = self.state["api_config"].get("model", "gpt-4o-mini")
        key = self.state["api_config"].get("api_key", "").strip()

        if mode == "real":
            method, path = self._parse_endpoint(endpoint)
            base_url = self.state["api_config"].get("api_base_url", "").strip()
            if path.startswith("http://") or path.startswith("https://"):
                url = path
            elif base_url:
                url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
            else:
                message = "Real mode requires API Base URL for relative endpoint paths."
                self._append_log(endpoint, safe_payload, mode="real", error=message)
                return {"ok": False, "error": message}

            headers = {
                "Content-Type": "application/json",
                "X-LLM-Provider": provider,
                "X-LLM-Model": model,
            }
            if key:
                headers["Authorization"] = f"Bearer {key}"

            try:
                response = requests.request(
                    method=method,
                    url=url,
                    json=payload_with_token,
                    headers=headers,
                    timeout=20,
                )
                if not response.ok:
                    message = f"HTTP {response.status_code}"
                    self._append_log(endpoint, safe_payload, mode="real", error=message)
                    return {"ok": False, "error": message}
                self._append_log(endpoint, safe_payload, mode="real")
                return {"ok": True, "data": response.text}
            except requests.RequestException as exc:
                message = str(exc)
                self._append_log(endpoint, safe_payload, mode="real", error=message)
                return {"ok": False, "error": message}

        time.sleep(0.12 + random.random() * 0.1)
        self._append_log(endpoint, safe_payload, mode="mock")
        return {"ok": True, "mode": "mock", "endpoint": endpoint}
