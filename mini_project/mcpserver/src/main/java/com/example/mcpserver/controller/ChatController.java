package com.example.mcpserver.controller;

import com.example.mcpserver.dto.chat.ChatHistoryItemResponse;
import com.example.mcpserver.dto.chat.ChatMessageRequest;
import com.example.mcpserver.dto.chat.ChatMessageResponse;
import com.example.mcpserver.service.chat.ChatService;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping({"/api/chat"})
public class ChatController {
   private final ChatService chatService;

   public ChatController(ChatService chatService) {
      this.chatService = chatService;
   }

   @GetMapping({"/messages"})
   public List<ChatHistoryItemResponse> getMessages(@RequestParam(required = false) String conversationId) {
      String resolvedConversationId = conversationId != null && !conversationId.isBlank() ? conversationId : "default-conversation";
      return this.chatService.getRecentMessages(resolvedConversationId);
   }

   @PostMapping({"/messages"})
   @ResponseStatus(HttpStatus.CREATED)
   public ChatMessageResponse createMessage(@RequestBody @Valid ChatMessageRequest request) {
      return this.chatService.ask(request);
   }
}