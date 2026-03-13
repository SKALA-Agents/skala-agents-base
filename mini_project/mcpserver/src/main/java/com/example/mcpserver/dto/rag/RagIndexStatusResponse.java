package com.example.mcpserver.dto.rag;

import java.time.Instant;
public record RagIndexStatusResponse(boolean ragEnabled, String startupMode, boolean vectorStoreExists, boolean metadataExists, boolean reindexRequired, String documentPath, String documentSha256, String embeddingModelId, Integer chunkCount, Instant indexedAt) {
}