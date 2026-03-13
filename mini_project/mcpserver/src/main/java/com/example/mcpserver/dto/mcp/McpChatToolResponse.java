package com.example.mcpserver.dto.mcp;

import com.example.mcpserver.dto.chat.StructuredChatAnswer;
public record McpChatToolResponse(Long userMessageId, Long assistantMessageId, String conversationId, String question, String answer, StructuredChatAnswer structuredAnswer) {
}