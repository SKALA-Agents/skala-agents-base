package com.example.mcpserver.config.chat;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.InMemoryChatMemoryRepository;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ChatClientConfig {
   @Bean
   public ChatClient chatClient(ChatClient.Builder chatClientBuilder) {
      return chatClientBuilder.build();
   }

   @Bean
   public ChatMemory chatMemory(ChatProperties chatProperties) {
      return MessageWindowChatMemory.builder().chatMemoryRepository(new InMemoryChatMemoryRepository()).maxMessages(chatProperties.memoryMaxMessages()).build();
   }
}