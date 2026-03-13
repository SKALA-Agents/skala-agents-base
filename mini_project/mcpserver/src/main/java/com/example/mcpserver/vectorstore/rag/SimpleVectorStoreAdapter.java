package com.example.mcpserver.vectorstore.rag;

import com.example.mcpserver.config.rag.RagProperties;
import java.io.File;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import org.springframework.ai.document.Document;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.SimpleVectorStore;
import org.springframework.stereotype.Component;

@Component
public class SimpleVectorStoreAdapter implements RagVectorStore {
   private final RagProperties ragProperties;
   private final EmbeddingModel embeddingModel;
   private SimpleVectorStore simpleVectorStore;

   public SimpleVectorStoreAdapter(RagProperties ragProperties, EmbeddingModel ragEmbeddingModel) {
      this.ragProperties = ragProperties;
      this.embeddingModel = ragEmbeddingModel;
      this.simpleVectorStore = this.createVectorStore();
   }

   public boolean exists() {
      return Path.of(this.ragProperties.vectorStorePath()).toFile().exists();
   }

   public void load() {
      this.simpleVectorStore = this.createVectorStore();
      this.simpleVectorStore.load(this.vectorStoreFile());
   }

   public void replaceAll(List<Document> documents) {
      this.prepareParentDirectory();
      this.simpleVectorStore = this.createVectorStore();
      this.simpleVectorStore.add(documents);
      this.simpleVectorStore.save(this.vectorStoreFile());
   }

   public List<Document> similaritySearch(SearchRequest searchRequest) {
      return this.simpleVectorStore.similaritySearch(searchRequest);
   }

   private File vectorStoreFile() {
      return Path.of(this.ragProperties.vectorStorePath()).toFile();
   }

   private void prepareParentDirectory() {
      try {
         Path parentPath = Path.of(this.ragProperties.vectorStorePath()).getParent();
         if (parentPath != null) {
            Files.createDirectories(parentPath);
         }

      } catch (IOException exception) {
         throw new UncheckedIOException("Failed to create vector store directory", exception);
      }
   }

   private SimpleVectorStore createVectorStore() {
      return SimpleVectorStore.builder(this.embeddingModel).build();
   }
}