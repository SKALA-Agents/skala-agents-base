package com.example.mcpserver.dto.mcp;

import com.example.mcpserver.dto.chat.StructuredChatAnswer;
import java.time.Instant;
public record McpToolExecutionResponse(String toolName, String conversationId, String question, String answer, StructuredChatAnswer structuredAnswer, Instant executedAt, boolean success) {
}