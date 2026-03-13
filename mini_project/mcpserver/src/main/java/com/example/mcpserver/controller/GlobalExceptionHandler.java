package com.example.mcpserver.controller;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.TimeoutException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.springframework.web.server.ResponseStatusException;

@RestControllerAdvice
public class GlobalExceptionHandler {
   @ExceptionHandler({MethodArgumentNotValidException.class})
   @ResponseStatus(HttpStatus.BAD_REQUEST)
   public Map<String, Object> handleValidationException(MethodArgumentNotValidException exception) {
      String message = (String)exception.getBindingResult().getFieldErrors().stream().findFirst().map((error) -> error.getDefaultMessage()).orElse("validation failed");
      return Map.of("status", HttpStatus.BAD_REQUEST.value(), "error", "Bad Request", "message", message, "timestamp", Instant.now());
   }

   @ExceptionHandler({ResponseStatusException.class})
   public ResponseEntity<Map<String, Object>> handleResponseStatusException(ResponseStatusException exception) {
      HttpStatus status = HttpStatus.resolve(exception.getStatusCode().value());
      if (status == null) {
         status = HttpStatus.INTERNAL_SERVER_ERROR;
      }

      return ResponseEntity.status(status).body(Map.of("status", status.value(), "error", status.getReasonPhrase(), "message", exception.getReason(), "timestamp", Instant.now()));
   }

   @ExceptionHandler({WebClientResponseException.class})
   public ResponseEntity<Map<String, Object>> handleWebClientResponseException(WebClientResponseException exception) {
      HttpStatus status = HttpStatus.resolve(exception.getStatusCode().value());
      if (status == null) {
         status = HttpStatus.BAD_GATEWAY;
      }

      return ResponseEntity.status(status).body(Map.of("status", status.value(), "error", status.getReasonPhrase(), "message", exception.getStatusText(), "timestamp", Instant.now()));
   }

   @ExceptionHandler({TimeoutException.class})
   public ResponseEntity<Map<String, Object>> handleTimeoutException(TimeoutException exception) {
      return ResponseEntity.status(HttpStatus.GATEWAY_TIMEOUT).body(Map.of("status", HttpStatus.GATEWAY_TIMEOUT.value(), "error", HttpStatus.GATEWAY_TIMEOUT.getReasonPhrase(), "message", "LLM request timed out", "timestamp", Instant.now()));
   }
}