package com.example.mcpserver.dto.chat;

import java.time.Instant;
public record ChatMessageResponse(Long userMessageId, Long assistantMessageId, String conversationId, String question, String answer, StructuredChatAnswer structuredAnswer, Instant answeredAt) {
}