package com.example.mcpserver.service.chat;

import com.example.mcpserver.dto.chat.ChatHistoryItemResponse;
import com.example.mcpserver.dto.chat.ChatMessageRequest;
import com.example.mcpserver.dto.chat.ChatMessageResponse;
import java.util.List;
public interface ChatService {
   ChatMessageResponse ask(ChatMessageRequest request);

   List<ChatHistoryItemResponse> getRecentMessages(String conversationId);
}