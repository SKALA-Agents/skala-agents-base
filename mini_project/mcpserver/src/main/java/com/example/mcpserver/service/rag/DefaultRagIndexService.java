package com.example.mcpserver.service.rag;

import com.example.mcpserver.config.rag.RagProperties;
import com.example.mcpserver.dto.rag.RagIndexMetadata;
import com.example.mcpserver.dto.rag.RagIndexStatusResponse;
import com.example.mcpserver.loader.rag.RagDocumentLoader;
import com.example.mcpserver.vectorstore.rag.RagVectorStore;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.document.Document;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.stereotype.Service;

@Service
@ConditionalOnProperty(
   prefix = "app.rag",
   name = {"enabled"},
   havingValue = "true",
   matchIfMissing = true
)
public class DefaultRagIndexService implements RagIndexService {
   private static final Logger log = LoggerFactory.getLogger(DefaultRagIndexService.class);
   private final RagProperties ragProperties;
   private final RagDocumentLoader ragDocumentLoader;
   private final RagVectorStore ragVectorStore;
   private final ObjectMapper objectMapper;

   public DefaultRagIndexService(RagProperties ragProperties, RagDocumentLoader ragDocumentLoader, RagVectorStore ragVectorStore, ObjectMapper objectMapper) {
      this.ragProperties = ragProperties;
      this.ragDocumentLoader = ragDocumentLoader;
      this.ragVectorStore = ragVectorStore;
      this.objectMapper = objectMapper;
   }

   @EventListener({ApplicationReadyEvent.class})
   public void initializeOnStartup() {
      switch (this.ragProperties.startupMode()) {
         case MANUAL:
            log.info("RAG startup mode is MANUAL. Skipping startup indexing.");
            break;
         case REINDEX:
            log.info("RAG startup mode is REINDEX. Rebuilding index.");
            this.reindex();
            break;
         case LOAD_OR_INDEX:
            if (this.ragVectorStore.exists() && !this.isReindexRequired()) {
               this.ragVectorStore.load();
               log.info("RAG vector store loaded without reindex.");
            } else {
               log.info("RAG index missing or stale. Rebuilding index.");
               this.reindex();
            }
      }

   }

   public RagIndexMetadata reindex() {
      List<Document> chunkedDocuments = this.ragDocumentLoader.loadChunkedDocuments();
      this.ragVectorStore.replaceAll(chunkedDocuments);
      RagIndexMetadata metadata = this.buildMetadata(chunkedDocuments.size());
      this.writeMetadata(metadata);
      log.info("RAG reindex completed: documentPath={}, chunks={}, startupMode={}", new Object[]{this.ragProperties.documentPath(), chunkedDocuments.size(), this.ragProperties.startupMode()});
      return metadata;
   }

   public RagIndexStatusResponse getStatus() {
      Optional<RagIndexMetadata> metadata = this.readMetadata();
      Integer chunkCount = (Integer)metadata.map(RagIndexMetadata::chunkCount).orElse(null);
      Instant indexedAt = (Instant)metadata.map(RagIndexMetadata::indexedAt).orElse(null);
      return new RagIndexStatusResponse(this.ragProperties.enabled(), this.ragProperties.startupMode().name(), this.ragVectorStore.exists(), this.metadataFileExists(), this.isReindexRequired(), this.ragProperties.documentPath(), (String)metadata.map(RagIndexMetadata::documentSha256).orElse(this.currentDocumentSha256()), this.ragProperties.embeddingModelId(), chunkCount, indexedAt);
   }

   public Optional<RagIndexMetadata> readMetadata() {
      Path metadataPath = Path.of(this.ragProperties.metadataPath());
      if (!metadataPath.toFile().exists()) {
         return Optional.empty();
      } else {
         try {
            return Optional.of((RagIndexMetadata)this.objectMapper.readValue(metadataPath.toFile(), RagIndexMetadata.class));
         } catch (IOException exception) {
            throw new UncheckedIOException("Failed to read RAG metadata", exception);
         }
      }
   }

   private boolean isReindexRequired() {
      if (!this.ragVectorStore.exists()) {
         return true;
      } else if (!this.isVectorStoreMetadataUsable()) {
         log.info("RAG vector store is missing required metadata (source/page). Reindexing.");
         return true;
      } else {
         return (Boolean)this.readMetadata().map((metadata) -> !metadata.documentSha256().equals(this.currentDocumentSha256()) || !metadata.embeddingModelId().equals(this.ragProperties.embeddingModelId()) || metadata.chunkSize() != this.ragProperties.chunkSize() || metadata.minChunkSizeChars() != this.ragProperties.minChunkSizeChars() || metadata.minChunkLengthToEmbed() != this.ragProperties.minChunkLengthToEmbed() || metadata.maxNumChunks() != this.ragProperties.maxNumChunks() || metadata.keepSeparator() != this.ragProperties.keepSeparator()).orElse(true);
      }
   }

   private boolean isVectorStoreMetadataUsable() {
      Path vectorStorePath = Path.of(this.ragProperties.vectorStorePath());
      if (!vectorStorePath.toFile().exists()) {
         return false;
      } else {
         try {
            Map<String, Object> rawStore = (Map)this.objectMapper.readValue(vectorStorePath.toFile(), new TypeReference<Map<String, Object>>() {
            });
            if (rawStore.isEmpty()) {
               return false;
            } else {
               for(Object value : rawStore.values()) {
                  if (!(value instanceof Map)) {
                     return false;
                  }

                  Map<?, ?> docMap = (Map)value;
                  Object metadataObject = docMap.get("metadata");
                  if (!(metadataObject instanceof Map)) {
                     return false;
                  }

                  Map<?, ?> metadata = (Map)metadataObject;
                  if (!metadata.containsKey("source")) {
                     return false;
                  }

                  if (!metadata.containsKey("pageNumber") && !metadata.containsKey("page") && !metadata.containsKey("page_number")) {
                     return false;
                  }
               }

               return true;
            }
         } catch (IOException exception) {
            log.warn("Failed to inspect RAG vector metadata file. Will reindex on startup. reason={}", exception.getMessage());
            return false;
         }
      }
   }

   private RagIndexMetadata buildMetadata(int chunkCount) {
      return new RagIndexMetadata(this.ragProperties.documentPath(), this.currentDocumentSha256(), this.ragProperties.embeddingModelId(), this.ragProperties.chunkSize(), this.ragProperties.minChunkSizeChars(), this.ragProperties.minChunkLengthToEmbed(), this.ragProperties.maxNumChunks(), this.ragProperties.keepSeparator(), chunkCount, Instant.now());
   }

   private void writeMetadata(RagIndexMetadata metadata) {
      Path metadataPath = Path.of(this.ragProperties.metadataPath());

      try {
         Path parent = metadataPath.getParent();
         if (parent != null) {
            Files.createDirectories(parent);
         }

         this.objectMapper.writerWithDefaultPrettyPrinter().writeValue(metadataPath.toFile(), metadata);
      } catch (IOException exception) {
         throw new UncheckedIOException("Failed to write RAG metadata", exception);
      }
   }

   private boolean metadataFileExists() {
      return Path.of(this.ragProperties.metadataPath()).toFile().exists();
   }

  private String currentDocumentSha256() {
      try {
         Resource documentResource = this.resolveDocumentResource(this.ragProperties.documentPath());
         byte[] bytes;
         try (InputStream input = documentResource.getInputStream()) {
            bytes = input.readAllBytes();
         }

         MessageDigest digest = MessageDigest.getInstance("SHA-256");
         return HexFormat.of().formatHex(digest.digest(bytes));
      } catch (IOException exception) {
         throw new UncheckedIOException("Failed to hash RAG document", exception);
      } catch (NoSuchAlgorithmException exception) {
         throw new IllegalStateException("SHA-256 algorithm is not available", exception);
      }
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

      if (Files.exists(Paths.get(path))) {
         throw new IllegalArgumentException("RAG document exists but cannot be opened as a resource path: " + path);
      }

      throw new IllegalArgumentException("RAG document file not found. Tried file path and classpath. documentPath=" + path);
   }

   private String trimLeadingSlash(String path) {
      String normalized = path == null ? "" : path.strip();
      if (normalized.startsWith("/")) {
         return normalized.substring(1);
      }
      return normalized;
   }
}
