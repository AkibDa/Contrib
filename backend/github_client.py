"""
Shared authenticated GitHub API client.
Uses GITHUB_TOKEN from environment if available.
Never logs or prints tokens.
"""

from __future__ import annotations

import os
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)


def get_github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Contrib-Evaluator/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token.strip()}"
    return headers


def create_github_client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(headers=get_github_headers(), timeout=timeout)


def create_async_github_client(timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(headers=get_github_headers(), timeout=timeout)
