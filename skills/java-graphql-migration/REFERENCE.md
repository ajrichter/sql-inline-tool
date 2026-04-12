# Java GraphQL Migration Quick Reference

## Dependencies

### HttpClient (built-in, Java 11+)

```xml
<!-- No extra dependency — java.net.http is in the JDK -->
<dependency>
    <groupId>com.fasterxml.jackson.core</groupId>
    <artifactId>jackson-databind</artifactId>
</dependency>
```

### Spring WebClient

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-webflux</artifactId>
</dependency>
```

### Spring GraphQL Client (Spring Boot 3.x)

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-graphql</artifactId>
</dependency>
```

## GraphQL Request Format

```json
{
  "query": "query Op($var: Type!) { field(arg: $var) { sub } }",
  "variables": { "var": "value" },
  "operationName": "Op"
}
```

## HttpClient Patterns

### Basic Query

```java
HttpClient client = HttpClient.newHttpClient();
String body = objectMapper.writeValueAsString(Map.of(
    "query", "{ users { id name } }"
));
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create(graphqlUrl))
    .header("Content-Type", "application/json")
    .header("Authorization", "Bearer " + token)
    .POST(HttpRequest.BodyPublishers.ofString(body))
    .build();
HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
```

### With Variables

```java
String body = objectMapper.writeValueAsString(Map.of(
    "query", "query($id: ID!) { user(id: $id) { name email } }",
    "variables", Map.of("id", userId)
));
```

### Async

```java
CompletableFuture<HttpResponse<String>> future =
    client.sendAsync(request, HttpResponse.BodyHandlers.ofString());
```

### Timeout

```java
HttpClient client = HttpClient.newBuilder()
    .connectTimeout(Duration.ofSeconds(5))
    .build();

HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create(graphqlUrl))
    .timeout(Duration.ofSeconds(10))
    .POST(HttpRequest.BodyPublishers.ofString(body))
    .build();
```

## WebClient Patterns

### Basic Query

```java
WebClient webClient = WebClient.builder()
    .baseUrl(graphqlUrl)
    .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
    .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + token)
    .build();

Mono<GraphQLResponse> result = webClient.post()
    .bodyValue(Map.of("query", "{ users { id name } }"))
    .retrieve()
    .bodyToMono(GraphQLResponse.class);
```

### With Variables

```java
Mono<GraphQLResponse> result = webClient.post()
    .bodyValue(Map.of(
        "query", "query($id: ID!) { user(id: $id) { name } }",
        "variables", Map.of("id", userId)
    ))
    .retrieve()
    .bodyToMono(GraphQLResponse.class);
```

### Blocking (bridge to non-reactive code)

```java
GraphQLResponse response = webClient.post()
    .bodyValue(requestBody)
    .retrieve()
    .bodyToMono(GraphQLResponse.class)
    .block(Duration.ofSeconds(10));
```

### Retry + Timeout

```java
Mono<GraphQLResponse> result = webClient.post()
    .bodyValue(requestBody)
    .retrieve()
    .bodyToMono(GraphQLResponse.class)
    .timeout(Duration.ofSeconds(10))
    .retryWhen(Retry.backoff(3, Duration.ofSeconds(1))
        .filter(ex -> ex instanceof WebClientResponseException.ServiceUnavailable));
```

### Error Handling

```java
Mono<GraphQLResponse> result = webClient.post()
    .bodyValue(requestBody)
    .retrieve()
    .onStatus(HttpStatusCode::is4xxClientError, resp ->
        resp.bodyToMono(String.class)
            .flatMap(body -> Mono.error(new GraphQLClientException(body))))
    .onStatus(HttpStatusCode::is5xxServerError, resp ->
        Mono.error(new GraphQLServerException("Server error")))
    .bodyToMono(GraphQLResponse.class);
```

### ExchangeFilterFunction (interceptor)

```java
WebClient webClient = WebClient.builder()
    .baseUrl(graphqlUrl)
    .filter(ExchangeFilterFunction.ofRequestProcessor(req -> {
        log.debug("GraphQL request: {}", req.url());
        return Mono.just(req);
    }))
    .filter(ExchangeFilterFunction.ofResponseProcessor(resp -> {
        log.debug("GraphQL response status: {}", resp.statusCode());
        return Mono.just(resp);
    }))
    .build();
```

## Response DTOs

```java
public record GraphQLResponse<T>(
    T data,
    List<GraphQLError> errors
) {}

public record GraphQLError(
    String message,
    List<Map<String, Object>> locations,
    List<Object> path,
    Map<String, Object> extensions
) {}
```

## Spring GraphQL Client (HttpGraphQlClient)

```java
// Setup
HttpGraphQlClient graphQlClient = HttpGraphQlClient.builder(webClient).build();

// Query
Mono<User> user = graphQlClient.document("{ user(id: 1) { name email } }")
    .retrieve("user")
    .toEntity(User.class);

// With variables
Mono<User> user = graphQlClient.document(
        "query($id: ID!) { user(id: $id) { name email } }")
    .variable("id", userId)
    .retrieve("user")
    .toEntity(User.class);

// Mutation
Mono<User> created = graphQlClient.document("""
        mutation($input: CreateUserInput!) {
            createUser(input: $input) { id name }
        }
    """)
    .variable("input", Map.of("name", "Alice", "email", "alice@example.com"))
    .retrieve("createUser")
    .toEntity(User.class);

// List result
Flux<User> users = graphQlClient.document("{ users { id name } }")
    .retrieve("users")
    .toEntityList(User.class)
    .flatMapMany(Flux::fromIterable);
```

## Migration Mapping

| HttpClient | WebClient Equivalent |
|-----------|---------------------|
| `HttpClient.newHttpClient()` | `WebClient.builder().build()` |
| `HttpClient.newBuilder().connectTimeout()` | `.clientConnector(new ReactorClientHttpConnector(HttpClient.create().responseTimeout()))` |
| `HttpRequest.newBuilder().uri()` | `WebClient.builder().baseUrl()` |
| `.header("Key", "val")` | `.defaultHeader("Key", "val")` |
| `.POST(BodyPublishers.ofString(body))` | `.post().bodyValue(body)` |
| `client.send(req, BodyHandlers.ofString())` | `.retrieve().bodyToMono(String.class)` |
| `client.sendAsync(req, handler)` | `.retrieve().bodyToMono()` (already async) |
| `response.statusCode()` | `.onStatus()` or `exchangeToMono()` |
| `response.body()` | `.bodyToMono()` / `.bodyToFlux()` |
| Try/catch blocks | `.onErrorResume()` / `.onErrorMap()` |
| `Thread.sleep()` + retry loop | `.retryWhen(Retry.backoff())` |
| `ExecutorService` thread pool | Reactor scheduler (automatic) |

## Common GraphQL Queries

### Query

```graphql
query GetUsers($limit: Int, $offset: Int) {
  users(limit: $limit, offset: $offset) {
    id
    name
    email
    roles { name }
  }
}
```

### Mutation

```graphql
mutation CreateUser($input: CreateUserInput!) {
  createUser(input: $input) {
    id
    name
  }
}
```

### Fragment

```graphql
fragment UserFields on User {
  id
  name
  email
}

query {
  users { ...UserFields }
}
```

### Subscription (WebSocket)

```graphql
subscription OnUserCreated {
  userCreated {
    id
    name
  }
}
```

## Connection Tuning

### HttpClient

```java
HttpClient client = HttpClient.newBuilder()
    .version(HttpClient.Version.HTTP_2)
    .connectTimeout(Duration.ofSeconds(5))
    .executor(Executors.newFixedThreadPool(10))
    .build();
```

### WebClient (Netty)

```java
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

ConnectionProvider provider = ConnectionProvider.builder("graphql")
    .maxConnections(50)
    .maxIdleTime(Duration.ofSeconds(20))
    .maxLifeTime(Duration.ofMinutes(5))
    .pendingAcquireTimeout(Duration.ofSeconds(10))
    .build();

HttpClient httpClient = HttpClient.create(provider)
    .responseTimeout(Duration.ofSeconds(10));

WebClient webClient = WebClient.builder()
    .baseUrl(graphqlUrl)
    .clientConnector(new ReactorClientHttpConnector(httpClient))
    .build();
```

## Testing

### MockWebServer

```java
MockWebServer server = new MockWebServer();
server.enqueue(new MockResponse()
    .setHeader("Content-Type", "application/json")
    .setBody("""
        { "data": { "user": { "id": "1", "name": "Alice" } } }
    """));
server.start();

WebClient testClient = WebClient.create(server.url("/graphql").toString());
```

### WireMock

```java
stubFor(post(urlEqualTo("/graphql"))
    .withHeader("Content-Type", containing("application/json"))
    .withRequestBody(containing("GetUser"))
    .willReturn(aResponse()
        .withHeader("Content-Type", "application/json")
        .withBody("""
            { "data": { "user": { "id": "1", "name": "Alice" } } }
        """)));
```

### StepVerifier (Reactor Test)

```java
Mono<User> result = graphqlClient.getUser("1");
StepVerifier.create(result)
    .expectNextMatches(user -> user.name().equals("Alice"))
    .verifyComplete();
```
