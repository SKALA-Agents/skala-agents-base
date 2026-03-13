package com.example.mcpserver.domain.chat;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(
   name = "chat_messages"
)
public class ChatMessage {
   @Id
   @GeneratedValue(
      strategy = GenerationType.IDENTITY
   )
   private Long id;
   @Enumerated(EnumType.STRING)
   @Column(
      nullable = false,
      length = 20
   )
   private ChatRole role;
   @Column(
      nullable = false,
      length = 100
   )
   private String conversationId;
   @Column(
      nullable = false,
      length = 4000
   )
   private String content;
   @Column(
      length = 10000
   )
   private String structuredContent;
   @Column(
      nullable = false
   )
   private Instant createdAt;

   protected ChatMessage() {
   }

   public ChatMessage(ChatRole role, String conversationId, String content, Instant createdAt) {
      this.role = role;
      this.conversationId = conversationId;
      this.content = content;
      this.createdAt = createdAt;
   }

   public ChatMessage(ChatRole role, String conversationId, String content, String structuredContent, Instant createdAt) {
      this.role = role;
      this.conversationId = conversationId;
      this.content = content;
      this.structuredContent = structuredContent;
      this.createdAt = createdAt;
   }

   public Long getId() {
      return this.id;
   }

   public ChatRole getRole() {
      return this.role;
   }

   public String getConversationId() {
      return this.conversationId;
   }

   public String getContent() {
      return this.content;
   }

   public String getStructuredContent() {
      return this.structuredContent;
   }

   public Instant getCreatedAt() {
      return this.createdAt;
   }
}