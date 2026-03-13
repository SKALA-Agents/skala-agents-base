package com.example.mcpserver.dto.rag;

import java.time.Instant;
public record RagIndexMetadata(String documentPath, String documentSha256, String embeddingModelId, int chunkSize, int minChunkSizeChars, int minChunkLengthToEmbed, int maxNumChunks, boolean keepSeparator, int chunkCount, Instant indexedAt) {
}