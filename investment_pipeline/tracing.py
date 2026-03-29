from __future__ import annotations

import os
from typing import Any


def parse_tags(raw_tags: str | None, *extra_tags: str) -> list[str]:
    tags: list[str] = []
    for value in [raw_tags, *extra_tags]:
        if not value:
            continue
        for tag in value.split(","):
            normalized = tag.strip()
            if normalized and normalized not in tags:
                tags.append(normalized)
    return tags


def apply_langsmith_env(
    *,
    enabled: bool,
    api_key: str | None,
    project: str | None,
    endpoint: str | None,
) -> None:
    if enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if api_key:
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ.setdefault("LANGSMITH_API_KEY", api_key)
    if project:
        os.environ["LANGCHAIN_PROJECT"] = project
        os.environ.setdefault("LANGSMITH_PROJECT", project)
    if endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
        os.environ.setdefault("LANGSMITH_ENDPOINT", endpoint)


def make_run_config(
    *,
    run_name: str,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {"run_name": run_name}
    if tags:
        config["tags"] = tags
    if metadata:
        config["metadata"] = metadata
    return config
