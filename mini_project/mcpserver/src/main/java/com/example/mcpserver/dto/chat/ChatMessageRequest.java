package com.example.mcpserver.dto.chat;

import jakarta.validation.constraints.NotBlank;
public record ChatMessageRequest(@NotBlank(
   message = "question must not be blank"
) String question, String conversationId) {
   public String resolvedConversationId() {
      return this.conversationId != null && !this.conversationId.isBlank() ? this.conversationId : "default-conversation";
   }
}