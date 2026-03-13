package com.example.mcpserver.loader.rag;

import com.example.mcpserver.config.rag.RagProperties;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.IntStream;
import org.springframework.ai.document.Document;
import org.springframework.ai.reader.ExtractedTextFormatter;
import org.springframework.ai.reader.pdf.PagePdfDocumentReader;
import org.springframework.ai.reader.pdf.config.PdfDocumentReaderConfig;
import org.springframework.ai.transformer.splitter.TokenTextSplitter;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.stereotype.Component;

@Component
public class SpringAiPdfDocumentLoader implements RagDocumentLoader {
   private final RagProperties ragProperties;
   private final TokenTextSplitter tokenTextSplitter;

   public SpringAiPdfDocumentLoader(RagProperties ragProperties, TokenTextSplitter tokenTextSplitter) {
      this.ragProperties = ragProperties;
      this.tokenTextSplitter = tokenTextSplitter;
   }

   public List<Document> loadPageDocuments() {
      Resource documentResource = this.resolveDocumentResource(this.ragProperties.documentPath());
      PagePdfDocumentReader reader = new PagePdfDocumentReader(documentResource, PdfDocumentReaderConfig.builder().withPagesPerDocument(1).withPageExtractedTextFormatter(ExtractedTextFormatter.builder().build()).build());
      List<Document> rawPages = reader.read();
      String sourceName = this.resolveSourceName(documentResource, this.ragProperties.documentPath());
      return IntStream.range(0, rawPages.size()).mapToObj((index) -> {
         Document document = (Document)rawPages.get(index);
         Map<String, Object> mergedMetadata = new HashMap(document.getMetadata());
         mergedMetadata.put("source", sourceName);
         mergedMetadata.put("sourcePath", this.ragProperties.documentPath());
         mergedMetadata.put("documentId", document.getId());
         mergedMetadata.put("page", index + 1);
         mergedMetadata.put("pageNumber", index + 1);
         mergedMetadata.put("page_number", index + 1);
         return Document.builder().id(this.normalizeDocumentId(document.getId(), index + 1)).text(document.getText()).metadata(mergedMetadata).build();
      }).toList();
   }

   private Resource resolveDocumentResource(String documentPath) {
      String path = documentPath == null ? "" : documentPath.strip();
      if (path.isEmpty()) {
         throw new IllegalArgumentException("RAG document path is not configured (app.rag.document-path)");
      }

      if (path.startsWith("classpath:")) {
         String classpathLocation = path.substring("classpath:".length());
         Resource classPathResource = new ClassPathResource(trimLeadingSlash(classpathLocation));
         if (!classPathResource.exists()) {
            throw new IllegalArgumentException("RAG document not found on classpath: " + classpathLocation);
         }
         return classPathResource;
      }

      if (path.startsWith("file:") || path.startsWith("http:") || path.startsWith("https:")) {
         try {
            Resource resource = new UrlResource(path);
            if (!resource.exists()) {
               throw new IllegalArgumentException("RAG document not found at: " + path);
            }

            return resource;
         } catch (Exception exception) {
            throw new IllegalArgumentException("Invalid RAG document resource: " + path, exception);
         }
      }

      Resource fileResource = new FileSystemResource(path);
      if (fileResource.exists()) {
         return fileResource;
      }

      Resource classPathResource = new ClassPathResource(trimLeadingSlash(path));
      if (classPathResource.exists()) {
         return classPathResource;
      }

      throw new IllegalArgumentException("RAG document file not found. Tried file path and classpath. documentPath=" + path);
   }

   private String resolveSourceName(Resource documentResource, String documentPath) {
      String filename = documentResource.getFilename();
      if (filename != null && !filename.isBlank()) {
         return filename;
      }

      Path sourcePath = Path.of(documentPath);
      if (sourcePath.getFileName() != null) {
         return sourcePath.getFileName().toString();
      }

      return documentPath;
   }

   private String trimLeadingSlash(String path) {
      String normalized = path == null ? "" : path.strip();
      if (normalized.startsWith("/")) {
         return normalized.substring(1);
      }

      return normalized;
   }

   public List<Document> loadChunkedDocuments() {
      List<Document> pageDocuments = this.loadPageDocuments();
      return pageDocuments.stream().flatMap((pageDocument) -> {
         Integer pageNumber = this.resolvePageNumber(pageDocument);
         List<Document> splitByPage = this.tokenTextSplitter.apply(List.of(pageDocument));
         return IntStream.range(0, splitByPage.size()).mapToObj((chunkIndex) -> {
            Document splitDocument = (Document)splitByPage.get(chunkIndex);
            Map<String, Object> mergedMetadata = new HashMap(pageDocument.getMetadata());
            mergedMetadata.putAll(splitDocument.getMetadata());
            mergedMetadata.put("pageNumber", pageNumber);
            mergedMetadata.put("chunkIndex", chunkIndex + 1);
            mergedMetadata.put("source", pageDocument.getMetadata().get("source"));
            mergedMetadata.put("page", pageNumber);
            mergedMetadata.put("page_number", pageNumber);
            return Document.builder().id(this.composeChunkId(splitDocument.getId(), pageNumber, chunkIndex + 1)).text(splitDocument.getText()).metadata(mergedMetadata).build();
         });
      }).toList();
   }

   private String normalizeDocumentId(String originalId, int pageNumber) {
      return originalId != null && !originalId.isBlank() ? originalId + "|page-" + pageNumber : "page-" + pageNumber;
   }

   private String composeChunkId(String splitDocId, Integer pageNumber, int chunkIndex) {
      String sanitizedPageSuffix = pageNumber == null ? "unknown" : pageNumber.toString();
      return splitDocId != null && !splitDocId.isBlank() ? splitDocId + "|page-" + sanitizedPageSuffix + "#chunk-" + chunkIndex : "page-" + sanitizedPageSuffix + "#chunk-" + chunkIndex;
   }

   private Integer resolvePageNumber(Document pageDocument) {
      return this.toInteger(pageDocument.getMetadata().get("pageNumber"));
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
}
