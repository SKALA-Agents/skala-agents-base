package com.example.mcpserver.controller;

import com.example.mcpserver.dto.chat.ChatHealthResponse;
import java.time.Instant;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping({"/api/chat"})
public class ChatHealthController {
   @GetMapping({"/health"})
   public ChatHealthResponse health() {
      return new ChatHealthResponse("UP", "chat-api-ready", Instant.now());
   }
}