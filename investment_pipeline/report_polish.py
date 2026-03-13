from __future__ import annotations

import re
from typing import List

from .llm import llm_client


SECTION_TRANSLATION_PROMPT = """
당신은 스타트업 투자심사 보고서를 다듬는 한국어 편집자다.

아래 Markdown 섹션을 자연스럽고 전문적인 한국어 투자 메모 문체로 다시 작성하라.

규칙:
- Markdown 구조, 제목, 표 형식, 회사명, 점수, URL은 유지한다.
- 영어 문장은 모두 한국어로 번역하거나 자연스러운 한국어 분석 문장으로 바꾼다.
- 웹페이지의 잡음(예: Skip to footer, sign in, org chart, navigation text)은 제거한다.
- 과도하게 긴 원문 스니펫은 1~3문장 길이의 한국어 요약으로 정리한다.
- 사실을 새로 만들지 말고, 제공된 내용만 정리한다.
- 출력은 섹션 전체 Markdown만 반환한다.
"""


def _split_sections(markdown: str) -> List[str]:
    parts = re.split(r"(?=^## )", markdown, flags=re.MULTILINE)
    return [part for part in parts if part.strip()]


def polish_report_to_korean(markdown: str) -> str:
    if not llm_client.available:
        return markdown

    sections = _split_sections(markdown)
    if not sections:
        return markdown

    polished_sections: List[str] = []
    for section in sections:
        if section.startswith("# DD-Worthiness"):
            polished_sections.append(section.strip())
            continue
        polished = llm_client.invoke_text(
            f"{SECTION_TRANSLATION_PROMPT}\n\n[Markdown Section]\n{section}"
        )
        polished_sections.append((polished or section).strip())

    header = ""
    if markdown.startswith("# "):
        header_parts = markdown.split("\n## ", 1)
        if len(header_parts) == 2:
            header = header_parts[0].strip()
            body_sections = _split_sections("## " + header_parts[1])
            polished_sections = []
            for section in body_sections:
                polished = llm_client.invoke_text(
                    f"{SECTION_TRANSLATION_PROMPT}\n\n[Markdown Section]\n{section}"
                )
                polished_sections.append((polished or section).strip())
            return header + "\n\n" + "\n\n".join(polished_sections) + "\n"

    return "\n\n".join(polished_sections) + "\n"
