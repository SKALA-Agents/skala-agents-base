package com.example.mcpserver.dto.chat;

import java.time.Instant;
public record ChatHealthResponse(String status, String message, Instant timestamp) {
}