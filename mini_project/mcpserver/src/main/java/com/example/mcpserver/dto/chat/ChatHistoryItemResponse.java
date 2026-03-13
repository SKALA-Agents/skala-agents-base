package com.example.mcpserver.dto.chat;

import java.time.Instant;
public record ChatHistoryItemResponse(Long id, String conversationId, String role, String content, StructuredChatAnswer structuredAnswer, Instant createdAt) {
}