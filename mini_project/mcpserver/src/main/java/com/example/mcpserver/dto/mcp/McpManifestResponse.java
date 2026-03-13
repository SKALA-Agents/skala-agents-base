package com.example.mcpserver.dto.mcp;

import java.util.List;
public record McpManifestResponse(List<McpToolDefinition> tools, List<McpResourceDefinition> resources, List<McpPromptDefinition> prompts) {
}