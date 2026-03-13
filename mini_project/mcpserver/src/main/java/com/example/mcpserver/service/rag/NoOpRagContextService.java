package com.example.mcpserver.service.rag;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

@Service
@ConditionalOnProperty(
   prefix = "app.rag",
   name = {"enabled"},
   havingValue = "false"
)
public class NoOpRagContextService implements RagContextService {
   public RagContext retrieveContext(String question) {
      return RagContext.disabled();
   }
}