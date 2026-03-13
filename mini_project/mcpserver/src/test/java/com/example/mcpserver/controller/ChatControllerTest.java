package com.example.mcpserver.controller;

import com.example.mcpserver.McpServerApplication;
import com.example.mcpserver.dto.chat.ChatHistoryItemResponse;
import com.example.mcpserver.dto.chat.ChatMessageRequest;
import com.example.mcpserver.dto.chat.ChatMessageResponse;
import com.example.mcpserver.dto.chat.SourceReference;
import com.example.mcpserver.dto.chat.StructuredChatAnswer;
import com.example.mcpserver.service.chat.ChatService;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentMatchers;
import org.mockito.BDDMockito;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;

@SpringBootTest(
   classes = {McpServerApplication.class}
)
@AutoConfigureMockMvc
class ChatControllerTest {
   @Autowired
   private MockMvc mockMvc;
   @MockBean
   private ChatService chatService;

   @Test
   void shouldReturnRecentMessages() throws Exception {
      BDDMockito.given(this.chatService.getRecentMessages("conv-123")).willReturn(List.of(new ChatHistoryItemResponse(1L, "conv-123", "USER", "Spring AI가 뭐야?", (StructuredChatAnswer)null, Instant.parse("2026-03-10T11:00:00Z")), new ChatHistoryItemResponse(2L, "conv-123", "ASSISTANT", "Spring AI는 LLM 애플리케이션 개발을 돕는 프레임워크입니다.", new StructuredChatAnswer("Spring AI 소개", "Spring AI는 스프링 기반 AI 애플리케이션 개발을 돕는 프로젝트입니다.", List.of("LLM 연동을 단순화합니다.", "Spring 생태계와 잘 통합됩니다."), List.of("Spring AI의 핵심 모듈은 무엇인가요?"), List.of(new SourceReference("docs/spring_AI_v1.0.pdf", 12, 3, "Spring AI provides abstractions for chat models and embeddings.")), true, "Answer grounded with 1 retrieved chunk(s) from spring_AI_v1.0.pdf."), Instant.parse("2026-03-10T11:00:02Z"))));
      this.mockMvc.perform(MockMvcRequestBuilders.get("/api/chat/messages", new Object[0]).param("conversationId", new String[]{"conv-123"})).andExpect(MockMvcResultMatchers.status().isOk()).andExpect(MockMvcResultMatchers.jsonPath("$[0].role", new Object[0]).value("USER")).andExpect(MockMvcResultMatchers.jsonPath("$[1].role", new Object[0]).value("ASSISTANT")).andExpect(MockMvcResultMatchers.jsonPath("$[1].structuredAnswer.title", new Object[0]).value("Spring AI 소개")).andExpect(MockMvcResultMatchers.jsonPath("$[1].structuredAnswer.sources[0].pageNumber", new Object[0]).value(12)).andExpect(MockMvcResultMatchers.jsonPath("$[1].structuredAnswer.usedRag", new Object[0]).value(true));
   }

   @Test
   void shouldCreateChatMessage() throws Exception {
      BDDMockito.given(this.chatService.ask((ChatMessageRequest)ArgumentMatchers.any(ChatMessageRequest.class))).willReturn(new ChatMessageResponse(1L, 2L, "conv-123", "Spring AI가 뭐야?", "Spring AI는 AI 통합을 위한 스프링 프로젝트입니다.", new StructuredChatAnswer("Spring AI란?", "Spring AI는 스프링 기반 AI 통합 프로젝트입니다.", List.of("OpenAI 등 다양한 모델을 연동할 수 있습니다."), List.of("Spring AI와 Spring Boot는 어떻게 함께 쓰나요?"), List.of(new SourceReference("docs/spring_AI_v1.0.pdf", 8, 1, "Spring AI supports model integrations through Spring abstractions.")), true, "Answer grounded with 1 retrieved chunk(s) from spring_AI_v1.0.pdf."), Instant.parse("2026-03-10T11:00:02Z")));
      this.mockMvc.perform(MockMvcRequestBuilders.post("/api/chat/messages", new Object[0]).contentType(MediaType.APPLICATION_JSON).content("{\n  \"question\": \"Spring AI가 뭐야?\",\n  \"conversationId\": \"conv-123\"\n}\n")).andExpect(MockMvcResultMatchers.status().isCreated()).andExpect(MockMvcResultMatchers.jsonPath("$.question", new Object[0]).value("Spring AI가 뭐야?")).andExpect(MockMvcResultMatchers.jsonPath("$.conversationId", new Object[0]).value("conv-123")).andExpect(MockMvcResultMatchers.jsonPath("$.answer", new Object[0]).value("Spring AI는 AI 통합을 위한 스프링 프로젝트입니다.")).andExpect(MockMvcResultMatchers.jsonPath("$.structuredAnswer.title", new Object[0]).value("Spring AI란?")).andExpect(MockMvcResultMatchers.jsonPath("$.structuredAnswer.sources[0].pageNumber", new Object[0]).value(8)).andExpect(MockMvcResultMatchers.jsonPath("$.structuredAnswer.usedRag", new Object[0]).value(true));
   }

   @Test
   void shouldRejectBlankQuestion() throws Exception {
      this.mockMvc.perform(MockMvcRequestBuilders.post("/api/chat/messages", new Object[0]).contentType(MediaType.APPLICATION_JSON).content("{\n  \"question\": \"   \"\n}\n")).andExpect(MockMvcResultMatchers.status().isBadRequest()).andExpect(MockMvcResultMatchers.jsonPath("$.message", new Object[0]).value("question must not be blank"));
   }
}