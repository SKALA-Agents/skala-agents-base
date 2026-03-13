package com.example.mcpserver.config.rag;

import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.transformer.splitter.TokenTextSplitter;
import org.springframework.ai.transformers.TransformersEmbeddingModel;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;

@Configuration
public class RagConfig {
   @Bean
   @Lazy
   public TokenTextSplitter tokenTextSplitter(RagProperties ragProperties) {
      return new TokenTextSplitter(ragProperties.chunkSize(), ragProperties.minChunkSizeChars(), ragProperties.minChunkLengthToEmbed(), ragProperties.maxNumChunks(), ragProperties.keepSeparator());
   }

   @Bean(
      name = {"ragEmbeddingModel"}
   )
   @Lazy
   public EmbeddingModel ragEmbeddingModel() {
      return new TransformersEmbeddingModel();
   }
}