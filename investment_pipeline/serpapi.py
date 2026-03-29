from __future__ import annotations

import json
from pathlib import Path
from typing import List

import requests
from requests import HTTPError

from .config import settings
from .models import ResearchEvidence


class SerpApiSearchClient:
    search_url = "https://serpapi.com/search.json"
    blocked_domains = {
        "linkedin.com",
        "www.linkedin.com",
        "medium.com",
        "www.medium.com",
        "wikipedia.org",
        "en.wikipedia.org",
        "tracxn.com",
        "www.tracxn.com",
        "superbcrew.com",
        "www.superbcrew.com",
    }

    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    @property
    def available(self) -> bool:
        return bool(self.api_key and settings.enable_live_research)

    def search(self, query: str, *, category: str, days: int = 3650) -> List[ResearchEvidence]:
        if not self.available:
            return []

        cache_dir = settings.research_cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = f"serpapi__{category}__{query}".replace("/", "_").replace(" ", "_")[:180]
        cache_file = cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return self._filter([ResearchEvidence.model_validate(item) for item in data])

        params = {
            "api_key": self.api_key,
            "engine": "google",
            "q": query,
            "num": settings.serpapi_max_results_per_query,
            "location": settings.serpapi_location,
            "google_domain": "google.com",
            "gl": "us",
            "hl": "en",
        }
        response = requests.get(self.search_url, params=params, timeout=20)
        if not response.ok:
            detail = response.text.strip()
            raise HTTPError(
                f"SerpApi search failed with status {response.status_code}: {detail}",
                response=response,
            )

        data = response.json()
        if data.get("error"):
            raise HTTPError(f"SerpApi search failed: {data['error']}", response=response)

        evidence: List[ResearchEvidence] = []
        for item in data.get("organic_results", []):
            url = item.get("link") or ""
            snippet = (item.get("snippet") or item.get("snippet_highlighted_words") or "").strip()
            if isinstance(snippet, list):
                snippet = " ".join(snippet)
            evidence.append(
                ResearchEvidence(
                    title=item.get("title") or query,
                    url=url,
                    source=url.split("/")[2] if url else "unknown",
                    published_date=None,
                    content=snippet,
                    score=item.get("position"),
                    category=category,
                )
            )

        cache_file.write_text(
            json.dumps([item.model_dump(mode="json") for item in evidence], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self._filter(evidence)

    def _filter(self, evidence: List[ResearchEvidence]) -> List[ResearchEvidence]:
        filtered: List[ResearchEvidence] = []
        seen_urls = set()
        for item in evidence:
            if not item.url:
                continue
            domain = item.source.lower()
            if any(domain.endswith(blocked) or domain == blocked for blocked in self.blocked_domains):
                continue
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            filtered.append(item)
        return filtered


serpapi_client = SerpApiSearchClient(settings.serpapi_api_key)
