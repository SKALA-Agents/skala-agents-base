from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def format_docs(docs: List[Document]) -> str:
    return "\n".join(
        [
            (
                f"<document><content>{doc.page_content}</content>"
                f"<source>{doc.metadata['source']}</source>"
                f"<page>{doc.metadata['page']}</page></document>"
            )
            for doc in docs
        ]
    )


@dataclass
class DesignDocumentKnowledgeBase:
    source_path: Path
    chunks: List[Document]

    @classmethod
    def from_markdown(cls, source_path: Path) -> "DesignDocumentKnowledgeBase":
        raw_text = source_path.read_text(encoding="utf-8")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=150,
            separators=["\n## ", "\n### ", "\n", " "],
        )
        split_texts = splitter.split_text(raw_text)
        docs = [
            Document(
                page_content=chunk,
                metadata={"source": str(source_path), "page": index + 1},
            )
            for index, chunk in enumerate(split_texts)
        ]
        return cls(source_path=source_path, chunks=docs)

    def search(self, query: str, limit: int = 4) -> List[Document]:
        query_terms = {term.lower() for term in query.split() if term.strip()}
        scored = []
        for doc in self.chunks:
            haystack = doc.page_content.lower()
            score = sum(1 for term in query_terms if term in haystack)
            scored.append((score, doc))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for score, doc in scored[:limit] if score > 0] or self.chunks[:limit]
