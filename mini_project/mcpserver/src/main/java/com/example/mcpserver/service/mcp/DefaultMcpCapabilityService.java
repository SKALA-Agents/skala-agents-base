package com.example.mcpserver.service.mcp;

import com.example.mcpserver.config.chat.ChatProperties;
import com.example.mcpserver.dto.chat.ChatMessageRequest;
import com.example.mcpserver.dto.chat.ChatMessageResponse;
import com.example.mcpserver.dto.mcp.McpChatToolResponse;
import com.example.mcpserver.dto.rag.RagIndexStatusResponse;
import com.example.mcpserver.service.chat.ChatService;
import com.example.mcpserver.service.rag.RagIndexService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.HashMap;
import java.util.Map;
import org.springaicommunity.mcp.annotation.McpArg;
import org.springaicommunity.mcp.annotation.McpPrompt;
import org.springaicommunity.mcp.annotation.McpResource;
import org.springaicommunity.mcp.annotation.McpTool;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

@Service
@ConditionalOnProperty(
   prefix = "spring.ai.mcp.server",
   name = {"enabled"},
   havingValue = "true",
   matchIfMissing = true
)
public class DefaultMcpCapabilityService {
   private static final String TOOL_SPRING_AI_CHAT = "spring-ai-chat";
   private static final String RESOURCE_RAG_STATUS = "resource://rag/status";
   private static final String RESOURCE_RAG_METADATA = "resource://rag/metadata";
   private static final String PROMPT_SPRING_AI_SYSTEM = "spring-ai-system-prompt";
   private final ChatService chatService;
   private final ChatProperties chatProperties;
   private final ObjectMapper objectMapper;
   private final ObjectProvider<RagIndexService> ragIndexServiceProvider;

   public DefaultMcpCapabilityService(ChatService chatService, ChatProperties chatProperties, ObjectMapper objectMapper, ObjectProvider<RagIndexService> ragIndexServiceProvider) {
      this.chatService = chatService;
      this.chatProperties = chatProperties;
      this.objectMapper = objectMapper;
      this.ragIndexServiceProvider = ragIndexServiceProvider;
   }

   @McpTool(
      name = "spring-ai-chat",
      title = "Spring AI Chat",
      description = "Spring AI 질문을 받아 채팅 응답을 구조화된 객체로 반환합니다.",
      generateOutputSchema = true
   )
   public McpChatToolResponse askSpringAi(@McpArg(name = "question",required = true,description = "사용자 질문") String question, @McpArg(name = "conversationId",required = false,description = "대화 문맥을 유지할 conversation ID") String conversationId) {
      ChatMessageResponse chatMessageResponse = this.chatService.ask(new ChatMessageRequest(question, conversationId));
      return new McpChatToolResponse(chatMessageResponse.userMessageId(), chatMessageResponse.assistantMessageId(), chatMessageResponse.conversationId(), chatMessageResponse.question(), chatMessageResponse.answer(), chatMessageResponse.structuredAnswer());
   }

   @McpResource(
      name = "rag-status",
      title = "RAG status",
      uri = "resource://rag/status",
      description = "현재 RAG 인덱스 상태(벡터스토어/메타데이터 존재 여부, 설정값) 조회",
      mimeType = "application/json"
   )
   public String readRagStatusResource() {
      RagIndexService service = (RagIndexService)this.ragIndexServiceProvider.getIfAvailable();
      if (service == null) {
         return "{\"ragEnabled\":false,\"status\":\"disabled\"}";
      } else {
         RagIndexStatusResponse status = service.getStatus();
         Map<String, Object> payload = new HashMap();
         payload.put("ragEnabled", status.ragEnabled());
         payload.put("startupMode", status.startupMode());
         payload.put("vectorStoreExists", status.vectorStoreExists());
         payload.put("metadataFileExists", status.metadataExists());
         payload.put("reindexRequired", status.reindexRequired());
         payload.put("documentPath", status.documentPath());
         payload.put("documentSha256", status.documentSha256());
         payload.put("embeddingModelId", status.embeddingModelId());
         payload.put("chunkCount", status.chunkCount());
         payload.put("indexedAt", status.indexedAt());
         return this.toJson(payload);
      }
   }

   @McpResource(
      name = "rag-metadata",
      title = "RAG metadata",
      uri = "resource://rag/metadata",
      description = "현재 인덱싱된 메타데이터(JSON) 조회",
      mimeType = "application/json"
   )
   public String readRagMetadataResource() {
      RagIndexService service = (RagIndexService)this.ragIndexServiceProvider.getIfAvailable();
      return service == null ? "{\"ragEnabled\":false,\"status\":\"metadata unavailable\"}" : (String)service.readMetadata().map((metadata) -> {
         try {
            return this.objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(metadata);
         } catch (JsonProcessingException var3) {
            return "{\"error\":\"RAG metadata serialization failed\"}";
         }
      }).orElse("{\"ragEnabled\":false,\"status\":\"metadata unavailable\"}");
   }

   @McpPrompt(
      name = "spring-ai-system-prompt",
      title = "Spring AI system prompt",
      description = "Spring AI 응답용 시스템 프롬프트"
   )
   public String springAiSystemPrompt() {
      return this.chatProperties.systemPrompt();
   }

   private String toJson(Map<String, Object> payload) {
      try {
         return this.objectMapper.writeValueAsString(payload);
      } catch (JsonProcessingException var3) {
         return "{\"error\":\"json serialization failed\"}";
      }
   }
}