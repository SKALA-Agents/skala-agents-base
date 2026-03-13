package com.example.mcpserver.dto.chat;

import java.util.List;
public record StructuredChatAnswer(String title, String summary, List<String> keyPoints, List<String> followUpQuestions, List<SourceReference> sources, boolean usedRag, String groundingNote) {
}