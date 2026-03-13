package com.example.mcpserver.config.chat;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

@Configuration
@EnableAsync
public class AsyncProcessingConfig {
   @Bean(
      name = {"chatEventExecutor"}
   )
   public ThreadPoolTaskExecutor chatEventExecutor() {
      ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
      executor.setCorePoolSize(2);
      executor.setMaxPoolSize(8);
      executor.setQueueCapacity(100);
      executor.setThreadNamePrefix("chat-event-");
      executor.initialize();
      return executor;
   }
}