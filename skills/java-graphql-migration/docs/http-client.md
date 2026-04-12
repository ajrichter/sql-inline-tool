# Java HttpClient for GraphQL

`java.net.http.HttpClient` (Java 11+) is the standard library HTTP client. It works well for GraphQL but is blocking by default and lacks built-in reactive/resilience features.

## Basic Setup

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import com.fasterxml.jackson.databind.ObjectMapper;

public class GraphQLClient {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String graphqlUrl;

    public GraphQLClient(String graphqlUrl) {
        this.graphqlUrl = graphqlUrl;
        this.objectMapper = new ObjectMapper();
        this.httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_2)
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    }
}
```

## Sending a Query

```java
public <T> T query(String query, Map<String, Object> variables, TypeReference<T> typeRef)
        throws IOException, InterruptedException {

    Map<String, Object> requestBody = new HashMap<>();
    requestBody.put("query", query);
    if (variables != null) {
        requestBody.put("variables", variables);
    }

    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create(graphqlUrl))
        .header("Content-Type", "application/json")
        .header("Accept", "application/json")
        .POST(HttpRequest.BodyPublishers.ofString(
            objectMapper.writeValueAsString(requestBody)))
        .build();

    HttpResponse<String> response = httpClient.send(
        request, HttpResponse.BodyHandlers.ofString());

    if (response.statusCode() != 200) {
        throw new RuntimeException("HTTP " + response.statusCode() + ": " + response.body());
    }

    return objectMapper.readValue(response.body(), typeRef);
}
```

## Authentication

### Bearer token

```java
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create(graphqlUrl))
    .header("Authorization", "Bearer " + accessToken)
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString(body))
    .build();
```

### API key

```java
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create(graphqlUrl))
    .header("X-API-Key", apiKey)
    .header("Content-Type", "application/json")
    .POST(HttpRequest.BodyPublishers.ofString(body))
    .build();
```

## Async Requests

```java
public CompletableFuture<JsonNode> queryAsync(String query, Map<String, Object> variables) {
    String body = objectMapper.writeValueAsString(
        Map.of("query", query, "variables", variables));

    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create(graphqlUrl))
        .header("Content-Type", "application/json")
        .POST(HttpRequest.BodyPublishers.ofString(body))
        .build();

    return httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString())
        .thenApply(HttpResponse::body)
        .thenApply(responseBody -> {
            try {
                return objectMapper.readTree(responseBody);
            } catch (JsonProcessingException e) {
                throw new UncheckedIOException(e);
            }
        });
}
```

## Retry Logic (Manual)

HttpClient has no built-in retry. You must implement it yourself:

```java
public HttpResponse<String> sendWithRetry(HttpRequest request, int maxRetries)
        throws IOException, InterruptedException {

    int attempt = 0;
    while (true) {
        try {
            HttpResponse<String> response = httpClient.send(
                request, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() < 500) {
                return response;
            }

            if (++attempt >= maxRetries) {
                return response;
            }
        } catch (IOException e) {
            if (++attempt >= maxRetries) {
                throw e;
            }
        }

        // Exponential backoff
        Thread.sleep((long) Math.pow(2, attempt) * 1000);
    }
}
```

## Timeout Configuration

```java
// Connection timeout (on the client)
HttpClient client = HttpClient.newBuilder()
    .connectTimeout(Duration.ofSeconds(5))
    .build();

// Request timeout (per request)
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create(graphqlUrl))
    .timeout(Duration.ofSeconds(30))
    .POST(HttpRequest.BodyPublishers.ofString(body))
    .build();
```

## Limitations

| Limitation | Impact |
|-----------|--------|
| Blocking by default | Ties up a thread per request |
| No connection pooling config | Limited tuning for high throughput |
| No retry/circuit breaker | Must implement manually |
| No reactive integration | Cannot compose with Reactor/RxJava |
| No request interceptors | Must wrap every call for logging/auth |
| No body auto-serialization | Must serialize JSON manually |

These limitations are the main reasons to migrate to WebClient.
