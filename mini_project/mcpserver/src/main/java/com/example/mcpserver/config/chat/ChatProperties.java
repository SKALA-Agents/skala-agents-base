package com.example.mcpserver.config.chat;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(
   prefix = "app.chat"
)
public record ChatProperties(String systemPrompt, int memoryMaxMessages, Integer llmTimeoutMs, Integer llmMaxAttempts, Long llmRetryBaseDelayMs, Long llmRetryMaxDelayMs, Long llmRetryJitterMs) {
   public int resolvedLlmTimeoutMs() {
      return this.llmTimeoutMs != null ? this.llmTimeoutMs : 15000;
   }

   public int resolvedLlmMaxAttempts() {
      return this.llmMaxAttempts != null && this.llmMaxAttempts >= 1 ? this.llmMaxAttempts : 3;
   }

   public long resolvedLlmRetryBaseDelayMs() {
      return this.llmRetryBaseDelayMs != null && this.llmRetryBaseDelayMs >= 0L ? this.llmRetryBaseDelayMs : 300L;
   }

   public long resolvedLlmRetryMaxDelayMs() {
      return this.llmRetryMaxDelayMs != null && this.llmRetryMaxDelayMs > 0L ? this.llmRetryMaxDelayMs : 2000L;
   }

   public long resolvedLlmRetryJitterMs() {
      return this.llmRetryJitterMs != null && this.llmRetryJitterMs >= 0L ? this.llmRetryJitterMs : 100L;
   }
}