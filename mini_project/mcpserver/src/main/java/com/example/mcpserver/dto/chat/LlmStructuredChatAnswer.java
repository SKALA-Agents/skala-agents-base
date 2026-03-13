package com.example.mcpserver.dto.chat;

import java.util.List;
public record LlmStructuredChatAnswer(String title, String summary, List<String> keyPoints, List<String> followUpQuestions) {
}