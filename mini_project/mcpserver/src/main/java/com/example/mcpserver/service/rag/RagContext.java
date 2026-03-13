package com.example.mcpserver.service.rag;

import com.example.mcpserver.dto.chat.SourceReference;
import java.util.List;
public record RagContext(boolean enabled, int matchCount, String contextText, List<SourceReference> sources) {
   public static RagContext disabled() {
      return new RagContext(false, 0, "", List.of());
   }
}