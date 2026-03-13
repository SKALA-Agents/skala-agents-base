package com.example.mcpserver.service.rag;

import com.example.mcpserver.dto.rag.RagIndexMetadata;
import com.example.mcpserver.dto.rag.RagIndexStatusResponse;
import java.util.Optional;
public interface RagIndexService {
   void initializeOnStartup();

   RagIndexMetadata reindex();

   RagIndexStatusResponse getStatus();

   Optional<RagIndexMetadata> readMetadata();
}