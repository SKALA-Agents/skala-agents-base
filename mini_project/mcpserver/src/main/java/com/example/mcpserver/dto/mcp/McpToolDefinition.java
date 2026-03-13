package com.example.mcpserver.dto.mcp;

import java.util.List;
public record McpToolDefinition(String name, String description, List<String> requiredArguments, String inputExample) {
}