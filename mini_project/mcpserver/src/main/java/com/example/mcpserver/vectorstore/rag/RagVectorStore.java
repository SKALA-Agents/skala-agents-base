package com.example.mcpserver.vectorstore.rag;

import java.util.List;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
public interface RagVectorStore {
   boolean exists();

   void load();

   void replaceAll(List<Document> documents);

   List<Document> similaritySearch(SearchRequest searchRequest);
}