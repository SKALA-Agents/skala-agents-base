package com.example.mcpserver.event.chat;

import com.example.mcpserver.dto.chat.ChatMessageRequest;
import com.example.mcpserver.dto.chat.ChatMessageResponse;
import java.util.concurrent.CompletableFuture;
public record ChatQueryEvent(String eventId, ChatMessageRequest request, CompletableFuture<ChatMessageResponse> responseFuture) {
}