package com.example.mcpserver.loader.rag;

import java.util.List;
import org.springframework.ai.document.Document;
public interface RagDocumentLoader {
   List<Document> loadPageDocuments();

   List<Document> loadChunkedDocuments();
}