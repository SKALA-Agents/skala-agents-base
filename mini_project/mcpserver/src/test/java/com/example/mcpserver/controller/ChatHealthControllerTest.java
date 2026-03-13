package com.example.mcpserver.controller;

import com.example.mcpserver.McpServerApplication;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;

@SpringBootTest(
   classes = {McpServerApplication.class}
)
@AutoConfigureMockMvc
class ChatHealthControllerTest {
   @Autowired
   private MockMvc mockMvc;

   @Test
   void shouldReturnHealthStatus() throws Exception {
      this.mockMvc.perform(MockMvcRequestBuilders.get("/api/chat/health", new Object[0])).andExpect(MockMvcResultMatchers.status().isOk()).andExpect(MockMvcResultMatchers.jsonPath("$.status", new Object[0]).value("UP")).andExpect(MockMvcResultMatchers.jsonPath("$.message", new Object[0]).value("chat-api-ready"));
   }
}