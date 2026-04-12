---
name: java-graphql-migration
description: Comprehensive guide for migrating Java GraphQL clients from legacy HTTP-based approaches to Spring WebClient (reactive). Covers HttpClient, Spring WebClient, GraphQL query construction, schema-first patterns, error handling, and side-by-side migration strategies. Use this skill when working with Java GraphQL APIs, migrating from RestTemplate/HttpClient to WebClient, or building reactive GraphQL clients in Spring Boot.
---

# Java GraphQL Migration

Migrate Java GraphQL client code from blocking HTTP clients (`java.net.http.HttpClient`, RestTemplate) to reactive Spring WebClient — or build new GraphQL integrations from scratch.

## Quick Start

### Old Way — Java HttpClient (blocking)

```java
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

HttpClient client = HttpClient.newHttpClient();
String query = """
    { "query": "{ users { id name email } }" }
    """;
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("https://api.example.com/graphql"))
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString(query))
    .build();
HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
```

### New Way — Spring WebClient (reactive)

```java
import org.springframework.web.reactive.function.client.WebClient;

WebClient webClient = WebClient.builder()
    .baseUrl("https://api.example.com/graphql")
    .defaultHeader("Content-Type", "application/json")
    .build();

Mono<String> result = webClient.post()
    .bodyValue(Map.of("query", "{ users { id name email } }"))
    .retrieve()
    .bodyToMono(String.class);
```

## Skill Contents

### Documentation
- `docs/core-concepts.md` - GraphQL over HTTP, query structure, variables, fragments
- `docs/http-client.md` - Java HttpClient patterns for GraphQL
- `docs/webclient.md` - Spring WebClient reactive patterns
- `docs/migration-patterns.md` - Step-by-step migration from HttpClient to WebClient
- `docs/error-handling.md` - GraphQL error handling, retries, timeouts
- `docs/testing.md` - Testing GraphQL clients with MockWebServer and WireMock

### Examples
- `examples/HttpClientGraphQL.java` - Complete HttpClient GraphQL client
- `examples/WebClientGraphQL.java` - Complete WebClient GraphQL client
- `examples/GraphQLQueryBuilder.java` - Type-safe query construction
- `examples/MigrationBefore.java` - Before migration (HttpClient)
- `examples/MigrationAfter.java` - After migration (WebClient)

### Templates
- `templates/HttpClientTemplate.java` - Starter HttpClient GraphQL client
- `templates/WebClientTemplate.java` - Starter WebClient GraphQL client

### Reference
- `REFERENCE.md` - Quick reference cheatsheet

## Key Concepts

### GraphQL Over HTTP

GraphQL APIs use a single POST endpoint. The request body contains:

```json
{
  "query": "query GetUser($id: ID!) { user(id: $id) { name email } }",
  "variables": { "id": "123" },
  "operationName": "GetUser"
}
```

The response always returns HTTP 200, even on errors:

```json
{
  "data": { "user": { "name": "Alice", "email": "alice@example.com" } },
  "errors": null
}
```

### Why Migrate to WebClient?

| Concern | HttpClient | WebClient |
|---------|-----------|-----------|
| Threading | Blocks thread per request | Non-blocking reactive |
| Backpressure | None | Built-in via Reactor |
| Connection pooling | Manual | Automatic via Netty |
| Retry/timeout | Manual loops | Declarative operators |
| Testability | Requires mocking HTTP | MockWebServer integration |
| Spring integration | Standalone | First-class Spring bean |
| Streaming | Limited | SSE, WebSocket, streaming |

### Migration Strategy

1. **Wrap first** — Keep HttpClient, wrap in `Mono.fromCallable()`
2. **Replace transport** — Swap HttpClient for WebClient, keep same DTOs
3. **Go reactive** — Return `Mono<T>` / `Flux<T>` from service methods
4. **Add resilience** — `retry()`, `timeout()`, circuit breakers

## When to Use This Skill

- Building a Java GraphQL client (any HTTP transport)
- Migrating from `java.net.http.HttpClient` to Spring `WebClient`
- Migrating from `RestTemplate` to `WebClient`
- Adding GraphQL queries/mutations to a Spring Boot application
- Setting up reactive GraphQL subscriptions
- Handling GraphQL errors, partial responses, and retries
