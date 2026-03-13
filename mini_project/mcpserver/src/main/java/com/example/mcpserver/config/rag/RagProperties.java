package com.example.mcpserver.config.rag;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(
   prefix = "app.rag"
)
public record RagProperties(boolean enabled, String documentPath, String vectorStorePath, String metadataPath, StartupMode startupMode, String embeddingModelId, int chunkSize, int minChunkSizeChars, int minChunkLengthToEmbed, int maxNumChunks, boolean keepSeparator, int topK, double similarityThreshold) {
   public static enum StartupMode {
      LOAD_OR_INDEX,
      REINDEX,
      MANUAL;

      // $FF: synthetic method
      private static StartupMode[] $values() {
         return new StartupMode[]{LOAD_OR_INDEX, REINDEX, MANUAL};
      }
   }
}