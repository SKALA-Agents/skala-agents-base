package com.example.mcpserver.config.chat;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties({ChatProperties.class})
public class ChatPropertiesConfig {
}