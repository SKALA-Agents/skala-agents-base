package com.example.mcpserver.dto.mcp;

import java.time.Instant;
public record McpResourceReadResponse(String uri, String name, String mimeType, String content, Instant readAt) {
}