package com.example.mcpserver.service.chat;

import com.example.mcpserver.config.chat.ChatProperties;
import com.example.mcpserver.domain.chat.ChatMessage;
import com.example.mcpserver.domain.chat.ChatRole;
import com.example.mcpserver.dto.chat.ChatHistoryItemResponse;
import com.example.mcpserver.dto.chat.ChatMessageRequest;
import com.example.mcpserver.dto.chat.ChatMessageResponse;
import com.example.mcpserver.dto.chat.LlmStructuredChatAnswer;
import com.example.mcpserver.dto.chat.SourceReference;
import com.example.mcpserver.dto.chat.StructuredChatAnswer;
import com.example.mcpserver.event.chat.ChatQueryEvent;
import com.example.mcpserver.repository.chat.ChatMessageRepository;
import com.example.mcpserver.service.rag.RagContext;
import com.example.mcpserver.service.rag.RagContextService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.client.advisor.api.Advisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.context.event.EventListener;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.springframework.web.server.ResponseStatusException;

@Service
public class OpenAiChatService implements ChatService {
   private static final Logger log = LoggerFactory.getLogger(OpenAiChatService.class);
   private final ChatClient chatClient;
   private final ChatProperties chatProperties;
   private final ChatMessageRepository chatMessageRepository;
   private final ObjectMapper objectMapper;
   private final RagContextService ragContextService;
   private final ChatMemory chatMemory;
   private final ApplicationEventPublisher eventPublisher;

   public OpenAiChatService(ChatClient chatClient, ChatProperties chatProperties, ChatMessageRepository chatMessageRepository, ObjectMapper objectMapper, RagContextService ragContextService, ChatMemory chatMemory, ApplicationEventPublisher eventPublisher) {
      this.chatClient = chatClient;
      this.chatProperties = chatProperties;
      this.chatMessageRepository = chatMessageRepository;
      this.objectMapper = objectMapper;
      this.ragContextService = ragContextService;
      this.chatMemory = chatMemory;
      this.eventPublisher = eventPublisher;
   }

   public ChatMessageResponse ask(ChatMessageRequest request) {
      CompletableFuture<ChatMessageResponse> responseFuture = new CompletableFuture();
      String eventId = UUID.randomUUID().toString();
      log.info("CHAT_EVENT_PUBLISHED [eventId={}] conversationId={} question={}", new Object[]{eventId, request.resolvedConversationId(), request.question()});
      this.eventPublisher.publishEvent(new ChatQueryEvent(eventId, request, responseFuture));

      try {
         return (ChatMessageResponse)responseFuture.get(this.resolveChatFlowTimeoutMs(), TimeUnit.MILLISECONDS);
      } catch (ExecutionException exception) {
         Throwable unwrapped = this.unwrapFailure(exception.getCause());
         log.warn("CHAT_EVENT_FAILED [eventId={}] {}", eventId, this.summarizeFailure(unwrapped));
         if (unwrapped instanceof ResponseStatusException statusException) {
            throw statusException;
         } else {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "채팅 이벤트 처리 중 오류가 발생했습니다.", unwrapped);
         }
      } catch (TimeoutException var8) {
         log.warn("CHAT_EVENT_TIMEOUT [eventId={} timeoutMs={}]", eventId, this.resolveChatFlowTimeoutMs());
         throw new ResponseStatusException(HttpStatus.GATEWAY_TIMEOUT, "채팅 응답 처리 시간이 초과되었습니다. 다시 시도해 주세요.");
      } catch (InterruptedException exception) {
         Thread.currentThread().interrupt();
         throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "요청이 인터럽트되어 중단되었습니다.", exception);
      }
   }

   @Async("chatEventExecutor")
   @EventListener
   @Transactional
   public void handleChatQuery(ChatQueryEvent event) {
      try {
         event.responseFuture().complete(this.processChatRequest(event.request()));
      } catch (Exception exception) {
         log.error("CHAT_EVENT_ERROR [eventId={}] {}", new Object[]{event.eventId(), exception.getMessage(), exception});
         event.responseFuture().completeExceptionally(exception);
      }

   }

   private ChatMessageResponse processChatRequest(ChatMessageRequest request) {
      long requestStartMs = System.currentTimeMillis();
      String conversationId = request.resolvedConversationId();
      Instant now = Instant.now();
      ChatMessage userMessage = (ChatMessage)this.chatMessageRepository.save(new ChatMessage(ChatRole.USER, conversationId, request.question(), now));
      log.info("LLM request: conversationId='{}', question='{}'", conversationId, request.question());
      log.debug("LLM system prompt: {}", this.chatProperties.systemPrompt());
      int historyContextSize = this.logHistoryContext(conversationId);
      RagContext ragContext = this.retrieveRagContextSafely(request.question(), conversationId);
      this.logRagContext(conversationId, ragContext);
      String userPrompt = this.buildUserPrompt(request.question(), ragContext);
      LlmCallResult llmResult = this.callLlmWithRetry(conversationId, userPrompt);
      LlmStructuredChatAnswer structuredAnswer = llmResult.answer();
      StructuredChatAnswer answerWithSources = new StructuredChatAnswer(structuredAnswer.title(), structuredAnswer.summary(), structuredAnswer.keyPoints(), structuredAnswer.followUpQuestions(), ragContext.sources(), ragContext.enabled() && ragContext.matchCount() > 0, this.buildGroundingNote(ragContext));
      log.info("LLM response: {}", this.toJson(answerWithSources));
      String answer = answerWithSources.summary();
      ChatMessage assistantMessage = (ChatMessage)this.chatMessageRepository.save(new ChatMessage(ChatRole.ASSISTANT, conversationId, answer, this.toJson(answerWithSources), Instant.now()));
      long requestElapsedMs = System.currentTimeMillis() - requestStartMs;
      log.info("LLM_METRIC [conversationId={}] totalDurationMs={} ragMatches={} historyEntries={} attempt={} llmCallDurationMs={}", new Object[]{conversationId, requestElapsedMs, ragContext.matchCount(), historyContextSize, llmResult.attempt(), llmResult.durationMs()});
      return new ChatMessageResponse(userMessage.getId(), assistantMessage.getId(), conversationId, userMessage.getContent(), assistantMessage.getContent(), answerWithSources, assistantMessage.getCreatedAt());
   }

   @Transactional(
      readOnly = true
   )
   public List<ChatHistoryItemResponse> getRecentMessages(String conversationId) {
      return this.chatMessageRepository.findTop20ByConversationIdOrderByCreatedAtDesc(conversationId).stream().sorted(Comparator.comparing(ChatMessage::getCreatedAt)).map((message) -> new ChatHistoryItemResponse(message.getId(), message.getConversationId(), message.getRole().name(), message.getContent(), this.parseStructuredAnswer(message.getStructuredContent()), message.getCreatedAt())).toList();
   }

   private LlmCallResult callLlmWithRetry(String conversationId, String prompt) {
      int maxAttempts = this.chatProperties.resolvedLlmMaxAttempts();
      Throwable lastFailure = null;
      int attempt = 1;

      while(true) {
         if (attempt <= maxAttempts) {
            long attemptStart = System.currentTimeMillis();

            try {
               log.info("LLM_CALL_START [conversationId={}, attempt={}/{} timeoutMs={}]", new Object[]{conversationId, attempt, maxAttempts, this.chatProperties.resolvedLlmTimeoutMs()});
               LlmStructuredChatAnswer answer = this.runLlmCallWithTimeout(conversationId, prompt);
               long attemptDurationMs = System.currentTimeMillis() - attemptStart;
               log.info("LLM_CALL_SUCCESS [conversationId={}, attempt={}, durationMs={}]", new Object[]{conversationId, attempt, attemptDurationMs});
               return new LlmCallResult(answer, attempt, attemptDurationMs);
            } catch (Exception exception) {
               lastFailure = this.unwrapFailure(exception);
               boolean retryable = this.isRetryableFailure(lastFailure);
               long attemptDurationMs = System.currentTimeMillis() - attemptStart;
               log.warn("LLM_CALL_ATTEMPT_FAILED [conversationId={}, attempt={}/{} durationMs={} retryable={}] {}", new Object[]{conversationId, attempt, maxAttempts, attemptDurationMs, retryable, this.summarizeFailure(lastFailure)});
               if (retryable && attempt != maxAttempts) {
                  long delayMs = this.nextRetryDelayMs(attempt);
                  this.sleepWithDelay(delayMs, conversationId, attempt);
                  ++attempt;
                  continue;
               }
            }
         }

         throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "LLM 호출 실패로 응답을 생성할 수 없습니다. 잠시 후 다시 시도해 주세요.", lastFailure);
      }
   }

   private LlmStructuredChatAnswer runLlmCallWithTimeout(String conversationId, String prompt) {
      try {
         return (LlmStructuredChatAnswer)CompletableFuture.supplyAsync(() -> (LlmStructuredChatAnswer)this.chatClient.prompt().advisors(new Advisor[]{MessageChatMemoryAdvisor.builder(this.chatMemory).conversationId(conversationId).build()}).system(this.chatProperties.systemPrompt()).user(prompt).call().entity(LlmStructuredChatAnswer.class)).orTimeout((long)this.chatProperties.resolvedLlmTimeoutMs(), TimeUnit.MILLISECONDS).join();
      } catch (CompletionException exception) {
         Throwable cause = exception.getCause();
         if (cause instanceof RuntimeException runtimeException) {
            throw runtimeException;
         } else {
            throw new IllegalStateException("LLM call failed", cause);
         }
      }
   }

   private boolean isRetryableFailure(Throwable throwable) {
      Throwable cause = this.unwrapFailure(throwable);
      if (cause instanceof WebClientResponseException webClientError) {
         int status = webClientError.getStatusCode().value();
         return status == 429 || status >= 500;
      } else {
         return cause instanceof TimeoutException || cause instanceof SocketTimeoutException || cause instanceof IOException || cause instanceof UnknownHostException || cause instanceof ConnectException;
      }
   }

   private long nextRetryDelayMs(int attempt) {
      long exponentialDelay = (long)((double)this.chatProperties.resolvedLlmRetryBaseDelayMs() * Math.pow((double)2.0F, (double)(attempt - 1)));
      long cappedDelay = Math.min(this.chatProperties.resolvedLlmRetryMaxDelayMs(), exponentialDelay);
      long jitter = this.chatProperties.resolvedLlmRetryJitterMs() == 0L ? 0L : ThreadLocalRandom.current().nextLong(0L, this.chatProperties.resolvedLlmRetryJitterMs() + 1L);
      return cappedDelay + jitter;
   }

   private void sleepWithDelay(long delayMs, String conversationId, int attempt) {
      if (delayMs > 0L) {
         try {
            log.info("LLM_CALL_RETRY_DELAY [conversationId={}, attempt={}] delayMs={}", new Object[]{conversationId, attempt, delayMs});
            Thread.sleep(delayMs);
         } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "LLM 호출 재시도 중 인터럽트가 발생했습니다.", exception);
         }
      }
   }

   private String summarizeFailure(Throwable throwable) {
      if (throwable == null) {
         return "unknown";
      } else {
         String var10000 = throwable.getClass().getSimpleName();
         return var10000 + ": " + throwable.getMessage();
      }
   }

   private Throwable unwrapFailure(Throwable throwable) {
      Throwable failure;
      for(failure = throwable; failure != null && failure.getCause() != null && failure instanceof CompletionException; failure = failure.getCause()) {
      }

      return failure;
   }

   private RagContext retrieveRagContextSafely(String question, String conversationId) {
      try {
         return this.ragContextService.retrieveContext(question);
      } catch (Exception exception) {
         log.warn("RAG_CONTEXT [conversationId={}] retrieval failed: {}", conversationId, exception.getMessage());
         return RagContext.disabled();
      }
   }

   private String toJson(StructuredChatAnswer structuredAnswer) {
      try {
         return this.objectMapper.writeValueAsString(structuredAnswer);
      } catch (JsonProcessingException exception) {
         throw new IllegalStateException("Failed to serialize structured answer", exception);
      }
   }

   private StructuredChatAnswer parseStructuredAnswer(String structuredContent) {
      if (structuredContent != null && !structuredContent.isBlank()) {
         try {
            return (StructuredChatAnswer)this.objectMapper.readValue(structuredContent, StructuredChatAnswer.class);
         } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Failed to deserialize structured answer", exception);
         }
      } else {
         return null;
      }
   }

   private String buildUserPrompt(String question, RagContext ragContext) {
      return ragContext.enabled() && ragContext.matchCount() != 0 ? "User question:\n%s\n\nReference context from spring_AI_v1.0.pdf:\n%s\n\nInstructions:\n- Prefer the reference context when it is relevant.\n- If the context is partial, state that briefly and fill the gap with your general Spring AI knowledge.\n- Keep the answer grounded in Spring AI.\n".formatted(question, ragContext.contextText()).trim() : "User question:\n%s\n\nNo reference context was retrieved from the RAG store.\nAnswer based on your Spring AI knowledge and say briefly if the reference document did not provide matching context.\n".formatted(question).trim();
   }

   private String buildGroundingNote(RagContext ragContext) {
      if (!ragContext.enabled()) {
         return "RAG is disabled for this response.";
      } else {
         return ragContext.matchCount() == 0 ? "No matching reference chunks were retrieved from the indexed PDF." : "Answer grounded with %d retrieved chunk(s) from spring_AI_v1.0.pdf.".formatted(ragContext.matchCount());
      }
   }

   private int logHistoryContext(String conversationId) {
      List<ChatMessage> recentMessages = this.chatMessageRepository.findByConversationIdOrderByCreatedAtDesc(conversationId, PageRequest.of(0, Math.max(1, this.chatProperties.memoryMaxMessages() + 1)));
      List<ChatMessage> historyMessages = recentMessages.stream().skip(1L).sorted(Comparator.comparing(ChatMessage::getCreatedAt)).toList();
      if (historyMessages.isEmpty()) {
         log.info("HISTORY_CONTEXT [conversationId={}] no prior messages found for context", conversationId);
         return 0;
      } else {
         log.info("HISTORY_CONTEXT [conversationId={}] {} entries", conversationId, historyMessages.size());

         for(ChatMessage message : historyMessages) {
            log.info("HISTORY_CONTEXT [conversationId={}] {} -> {}", new Object[]{conversationId, message.getRole().name(), this.abbreviate(message.getContent(), 200)});
         }

         return historyMessages.size();
      }
   }

   private void logRagContext(String conversationId, RagContext ragContext) {
      log.info("RAG_CONTEXT [conversationId={}] enabled={}, matchCount={}", new Object[]{conversationId, ragContext.enabled(), ragContext.matchCount()});
      if (ragContext.enabled() && ragContext.matchCount() != 0) {
         for(SourceReference source : ragContext.sources()) {
            log.info("RAG_CONTEXT [conversationId={}] source={} page={} snippet={}", new Object[]{conversationId, source.source(), source.pageNumber(), this.abbreviate(source.snippet(), 200)});
         }

      }
   }

   private String abbreviate(String text, int maxLength) {
      if (text != null && !text.isBlank()) {
         if (text.length() <= maxLength) {
            return text;
         } else {
            String var10000 = text.substring(0, maxLength);
            return var10000.trim() + "...";
         }
      } else {
         return "";
      }
   }

   private long resolveChatFlowTimeoutMs() {
      return (long)((double)(this.chatProperties.resolvedLlmTimeoutMs() * Math.max(1, this.chatProperties.resolvedLlmMaxAttempts())) * 2.2);
   }

   private static record LlmCallResult(LlmStructuredChatAnswer answer, int attempt, long durationMs) {
   }
}