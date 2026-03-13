package com.example.mcpserver.controller;

import com.example.mcpserver.dto.rag.RagIndexMetadata;
import com.example.mcpserver.dto.rag.RagIndexStatusResponse;
import com.example.mcpserver.service.rag.RagIndexService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping({"/api/rag"})
@ConditionalOnProperty(
   prefix = "app.rag",
   name = {"enabled"},
   havingValue = "true",
   matchIfMissing = true
)
public class RagAdminController {
   private final RagIndexService ragIndexService;

   public RagAdminController(RagIndexService ragIndexService) {
      this.ragIndexService = ragIndexService;
   }

   @GetMapping({"/status"})
   public RagIndexStatusResponse getStatus() {
      return this.ragIndexService.getStatus();
   }

   @PostMapping({"/reindex"})
   @ResponseStatus(HttpStatus.ACCEPTED)
   public RagIndexMetadata reindex() {
      return this.ragIndexService.reindex();
   }
}