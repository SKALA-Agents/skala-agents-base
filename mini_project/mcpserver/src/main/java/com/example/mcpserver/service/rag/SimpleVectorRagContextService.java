package com.example.mcpserver.service.rag;

import com.example.mcpserver.config.rag.RagProperties;
import com.example.mcpserver.dto.chat.SourceReference;
import com.example.mcpserver.vectorstore.rag.RagVectorStore;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

@Service
@ConditionalOnProperty(
   prefix = "app.rag",
   name = {"enabled"},
   havingValue = "true",
   matchIfMissing = true
)
public class SimpleVectorRagContextService implements RagContextService {
   private static final Logger log = LoggerFactory.getLogger(SimpleVectorRagContextService.class);
   private final RagVectorStore ragVectorStore;
   private final RagProperties ragProperties;

   public SimpleVectorRagContextService(RagVectorStore ragVectorStore, RagProperties ragProperties) {
      this.ragVectorStore = ragVectorStore;
      this.ragProperties = ragProperties;
   }

   public RagContext retrieveContext(String question) {
      List<Document> documents = this.ragVectorStore.similaritySearch(SearchRequest.builder().query(question).topK(this.ragProperties.topK()).similarityThreshold(this.ragProperties.similarityThreshold()).build());
      log.info("RAG retrieval: question='{}', matches={}", question, documents.size());
      String contextText = (String)documents.stream().map(this::formatDocument).collect(Collectors.joining("\n\n"));
      List<SourceReference> sources = documents.stream().map(this::toSourceReference).toList();
      return new RagContext(true, documents.size(), contextText, sources);
   }

   private String formatDocument(Document document) {
      Object pageNumber = this.resolvePageNumber(document);
      return "[source=%s, page=%s]\n%s\n".formatted(this.resolveSource(document), pageNumber, document.getText()).trim();
   }

   private SourceReference toSourceReference(Document document) {
      return new SourceReference(this.resolveSource(document), this.resolvePageNumber(document), this.abbreviate(document.getText(), 220));
   }

   private String resolveSource(Document document) {
      String source = this.resolveText(document.getMetadata(), List.of("source", "documentSource", "file_name", "filename", "fileName"));
      if (source != null) {
         return source;
      } else {
         String fallback = Path.of(this.ragProperties.documentPath()).getFileName().toString();
         return fallback == null ? "unknown" : fallback;
      }
   }

   private Integer resolvePageNumber(Document document) {
      Object resolved = this.resolveValue(document.getMetadata(), List.of("pageNumber", "page_number", "page"));
      Integer pageNumber = this.toInteger(resolved);
      return pageNumber != null ? pageNumber : this.parsePageFromId(document.getId());
   }

   private Integer parsePageFromId(String documentId) {
      if (documentId == null) {
         return null;
      } else {
         String pageMarker = "|page-";
         int markerIndex = documentId.lastIndexOf(pageMarker);
         if (markerIndex < 0) {
            return null;
         } else {
            int startIndex = markerIndex + pageMarker.length();
            int endIndex = documentId.indexOf(35, startIndex);
            if (endIndex < 0) {
               endIndex = documentId.length();
            }

            try {
               return Integer.parseInt(documentId.substring(startIndex, endIndex));
            } catch (NumberFormatException var7) {
               return null;
            }
         }
      }
   }

   private Integer toInteger(Object value) {
      if (value == null) {
         return null;
      } else if (value instanceof Number) {
         Number number = (Number)value;
         return number.intValue();
      } else {
         try {
            return Integer.parseInt(String.valueOf(value));
         } catch (NumberFormatException var3) {
            return null;
         }
      }
   }

   private String resolveText(Map<String, Object> metadata, List<String> keys) {
      for(String key : keys) {
         Object value = metadata.get(key);
         if (value != null) {
            String text = String.valueOf(value).trim();
            if (!text.isBlank()) {
               return text;
            }
         }
      }

      return null;
   }

   private Object resolveValue(Map<String, Object> metadata, List<String> keys) {
      for(String key : keys) {
         Object value = metadata.get(key);
         if (value != null) {
            return value;
         }
      }

      return null;
   }

   private String abbreviate(String text, int maxLength) {
      if (text != null && text.length() > maxLength) {
         String var10000 = text.substring(0, maxLength);
         return var10000.trim() + "...";
      } else {
         return text;
      }
   }
}