package com.example.mcpserver.repository.chat;

import com.example.mcpserver.domain.chat.ChatMessage;
import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
public interface ChatMessageRepository extends JpaRepository<ChatMessage, Long> {
   List<ChatMessage> findByConversationIdOrderByCreatedAtDesc(String conversationId, Pageable pageable);

   List<ChatMessage> findTop20ByConversationIdOrderByCreatedAtDesc(String conversationId);
}