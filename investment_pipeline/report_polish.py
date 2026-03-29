from __future__ import annotations

from .llm import llm_client


FULL_REPORT_TRANSLATION_PROMPT = """
You are a Korean editor finalizing a startup investment screening report.

Rewrite the entire Markdown report using the following rules.

Rules:
- Preserve the Markdown structure and headings.
- Keep all section titles and table-of-contents headers in English exactly as written.
- Rewrite all body paragraphs, bullets, and explanatory sentences beneath headings in Korean.
- Preserve table headers, company names, Series labels, scores, URLs, and REFERENCE entries.
- Do not leave English prose in the body text, except for company names, Series, DD-Worthiness, Selective DD, REFERENCE, table headers, and URLs.
- Remove English webpage snippets, navigation text, and obvious noise.
- Rewrite long raw excerpts into natural Korean VC-style memo prose in 1-3 sentences.
- Rewrite each company's Executive Overview, Technology Assessment, Market Position, and Risk Assessment as complete Korean analytical paragraphs.
- Do not invent new facts; organize only the provided content.
- Preserve the REFERENCE format and links.
- Return only the final Markdown body.
"""


def polish_report_to_korean(markdown: str) -> str:
    if not llm_client.available:
        return markdown

    polished = llm_client.invoke_text(
        f"{FULL_REPORT_TRANSLATION_PROMPT}\n\n[Markdown Report]\n{markdown}"
    )
    return (polished or markdown).strip() + "\n"
