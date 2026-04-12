# Error Handling for GraphQL Clients

## GraphQL Error Model

GraphQL has two layers of errors:

1. **HTTP-level**: Connection failures, 401/403/500 status codes
2. **GraphQL-level**: Errors in the response body (always HTTP 200)

```json
{
  "data": { "user": null },
  "errors": [
    {
      "message": "User not found",
      "locations": [{ "line": 1, "column": 3 }],
      "path": ["user"],
      "extensions": {
        "code": "NOT_FOUND",
        "timestamp": "2024-01-15T10:30:00Z"
      }
    }
  ]
}
```

## Error Response DTOs

```java
public record GraphQLResponse<T>(T data, List<GraphQLError> errors) {

    public boolean hasErrors() {
        return errors != null && !errors.isEmpty();
    }

    public T dataOrThrow() {
        if (hasErrors()) {
            throw new GraphQLException(errors.get(0).message());
        }
        return data;
    }
}

public record GraphQLError(
    String message,
    List<Location> locations,
    List<Object> path,
    Map<String, Object> extensions
) {
    public record Location(int line, int column) {}

    public String code() {
        if (extensions == null) return null;
        return (String) extensions.get("code");
    }
}

public class GraphQLException extends RuntimeException {
    private final List<GraphQLError> errors;

    public GraphQLException(String message) {
        super(message);
        this.errors = List.of();
    }

    public GraphQLException(List<GraphQLError> errors) {
        super(errors.isEmpty() ? "Unknown error" : errors.get(0).message());
        this.errors = errors;
    }

    public List<GraphQLError> getErrors() { return errors; }
}
```

## HttpClient Error Handling

```java
public <T> T query(String query, Map<String, Object> variables, TypeReference<T> typeRef)
        throws IOException, InterruptedException {

    HttpResponse<String> response = httpClient.send(request,
        HttpResponse.BodyHandlers.ofString());

    // Layer 1: HTTP errors
    if (response.statusCode() == 401) {
        throw new AuthenticationException("Invalid credentials");
    }
    if (response.statusCode() >= 400) {
        throw new GraphQLException("HTTP " + response.statusCode() + ": " + response.body());
    }

    // Layer 2: GraphQL errors
    GraphQLResponse<T> parsed = objectMapper.readValue(response.body(), typeRef);
    if (parsed.hasErrors()) {
        // Decide: throw or return partial data
        if (parsed.data() == null) {
            throw new GraphQLException(parsed.errors());
        }
        // Log partial errors but return data
        log.warn("GraphQL partial errors: {}", parsed.errors());
    }

    return parsed;
}
```

## WebClient Error Handling

```java
public Mono<User> getUser(String id) {
    return webClient.post()
        .bodyValue(requestBody(id))
        .retrieve()
        // Layer 1: HTTP errors
        .onStatus(HttpStatusCode::is4xxClientError, response ->
            response.bodyToMono(String.class)
                .flatMap(body -> Mono.error(new GraphQLException("Client error: " + body))))
        .onStatus(HttpStatusCode::is5xxServerError, response ->
            Mono.error(new GraphQLException("Server error")))
        .bodyToMono(new ParameterizedTypeReference<GraphQLResponse<UserData>>() {})
        // Layer 2: GraphQL errors
        .flatMap(response -> {
            if (response.hasErrors() && response.data() == null) {
                return Mono.error(new GraphQLException(response.errors()));
            }
            return Mono.justOrEmpty(response.data().user());
        });
}
```

## Partial Responses

GraphQL can return both data AND errors. Decide per use case:

```java
// Strategy 1: Fail on any error
public Mono<User> getUserStrict(String id) {
    return executeQuery(id)
        .flatMap(resp -> resp.hasErrors()
            ? Mono.error(new GraphQLException(resp.errors()))
            : Mono.justOrEmpty(resp.data().user()));
}

// Strategy 2: Accept partial data, log errors
public Mono<User> getUserLenient(String id) {
    return executeQuery(id)
        .doOnNext(resp -> {
            if (resp.hasErrors()) {
                log.warn("Partial GraphQL errors for user {}: {}", id, resp.errors());
            }
        })
        .map(resp -> resp.data().user());
}
```

## Timeout Patterns

### HttpClient

```java
try {
    HttpResponse<String> response = httpClient.send(request,
        HttpResponse.BodyHandlers.ofString());
} catch (HttpTimeoutException e) {
    throw new GraphQLException("Request timed out");
}
```

### WebClient

```java
webClient.post()
    .bodyValue(requestBody)
    .retrieve()
    .bodyToMono(GraphQLResponse.class)
    .timeout(Duration.ofSeconds(10))
    .onErrorMap(TimeoutException.class,
        ex -> new GraphQLException("GraphQL query timed out after 10s"));
```

## Retry Patterns

### WebClient (declarative)

```java
.retryWhen(Retry.backoff(3, Duration.ofSeconds(1))
    .maxBackoff(Duration.ofSeconds(10))
    .jitter(0.5)
    .filter(ex -> isRetryable(ex))
    .doBeforeRetry(signal ->
        log.warn("Retrying GraphQL query, attempt {}", signal.totalRetries() + 1))
    .onRetryExhaustedThrow((spec, signal) ->
        new GraphQLException("Exhausted retries", signal.failure())))

private boolean isRetryable(Throwable ex) {
    if (ex instanceof WebClientResponseException wcre) {
        int status = wcre.getStatusCode().value();
        return status == 429 || status >= 500;
    }
    return ex instanceof ConnectException
        || ex instanceof TimeoutException;
}
```

## Error Classification

| Error Type | HTTP Status | Retry? | Action |
|-----------|-------------|--------|--------|
| Query syntax error | 200 (GraphQL error) | No | Fix query |
| Variable type mismatch | 200 (GraphQL error) | No | Fix variables |
| Not found | 200 (GraphQL error) | No | Return empty/404 |
| Auth failure | 401 | No* | Refresh token, then retry |
| Rate limited | 429 | Yes | Backoff and retry |
| Server error | 500 | Yes | Retry with backoff |
| Connection refused | N/A | Yes | Retry with backoff |
| Timeout | N/A | Yes | Retry with backoff |
