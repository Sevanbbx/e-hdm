from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .exceptions import EHDMTransportError


@dataclass(slots=True)
class SSLConfig:
    cert: str | None = None
    key: str | None = None
    verify: str | bool | None = True

    def build_context(self) -> ssl.SSLContext:
        if self.verify is False:
            context = ssl._create_unverified_context()
        else:
            context = ssl.create_default_context(cafile=self.verify if isinstance(self.verify, str) else None)
        if self.cert:
            context.load_cert_chain(certfile=self.cert, keyfile=self.key)
        return context


class SyncTransport:
    def __init__(self, ssl_config: SSLConfig) -> None:
        self._ssl_config = ssl_config

    def post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, context=self._ssl_config.build_context()) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise EHDMTransportError(str(exc)) from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EHDMTransportError(f"Invalid JSON response: {raw!r}") from exc

