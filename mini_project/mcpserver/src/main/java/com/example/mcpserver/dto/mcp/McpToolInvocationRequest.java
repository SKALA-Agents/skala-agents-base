package com.example.mcpserver.dto.mcp;

import java.util.Map;
public record McpToolInvocationRequest(String conversationId, Map<String, String> arguments) {
}