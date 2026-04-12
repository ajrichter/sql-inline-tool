# Migration Patterns: HttpClient to WebClient

## Overview

Migration can be done incrementally. You don't need to rewrite everything at once.

### Migration Stages

```
Stage 1: Wrap HttpClient in Mono       (minimal change, immediate reactive compat)
Stage 2: Replace with WebClient          (new transport, same DTOs)
Stage 3: Return reactive types           (Mono/Flux from services)
Stage 4: Add resilience                  (retry, timeout, circuit breaker)
```

## Stage 1: Wrap Existing HttpClient

The smallest possible change — wrap blocking calls in `Mono.fromCallable()`:

### Before

```java
public User getUser(String id) throws IOException, InterruptedException {
    String body = objectMapper.writeValueAsString(Map.of(
        "query", "query($id: ID!) { user(id: $id) { id name email } }",
        "variables", Map.of("id", id)
    ));

    HttpRequest request = HttpRequest.newBuilder()
        .uri(URI.create(graphqlUrl))
        .header("Content-Type", "application/json")
        .POST(HttpRequest.BodyPublishers.ofString(body))
        .build();

    HttpResponse<String> response = httpClient.send(request,
        HttpResponse.BodyHandlers.ofString());

    GraphQLResponse<UserData> parsed = objectMapper.readValue(
        response.body(), new TypeReference<>() {});
    return parsed.data().user();
}
```

### After (Stage 1 — wrapped)

```java
public Mono<User> getUser(String id) {
    return Mono.fromCallable(() -> {
        String body = objectMapper.writeValueAsString(Map.of(
            "query", "query($id: ID!) { user(id: $id) { id name email } }",
            "variables", Map.of("id", id)
        ));

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(graphqlUrl))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();

        HttpResponse<String> response = httpClient.send(request,
            HttpResponse.BodyHandlers.ofString());

        GraphQLResponse<UserData> parsed = objectMapper.readValue(
            response.body(), new TypeReference<>() {});
        return parsed.data().user();
    }).subscribeOn(Schedulers.boundedElastic());
}
```

**What changed**: Return type is `Mono<User>`, blocking call runs on elastic scheduler. Callers can now compose reactively.

## Stage 2: Replace with WebClient

Swap the HTTP transport while keeping the same return types and DTOs:

```java
private final WebClient webClient;

public GraphQLService(WebClient.Builder webClientBuilder,
                      @Value("${graphql.url}") String graphqlUrl) {
    this.webClient = webClientBuilder
        .baseUrl(graphqlUrl)
        .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
        .build();
}

public Mono<User> getUser(String id) {
    return webClient.post()
        .bodyValue(Map.of(
            "query", "query($id: ID!) { user(id: $id) { id name email } }",
            "variables", Map.of("id", id)
        ))
        .retrieve()
        .bodyToMono(new ParameterizedTypeReference<GraphQLResponse<UserData>>() {})
        .map(response -> response.data().user());
}
```

**What changed**: `HttpClient` replaced with `WebClient`. No more manual request building, no `ObjectMapper` for request serialization.

## Stage 3: Reactive Throughout

Update service interfaces and callers to work with `Mono`/`Flux`:

### Service Interface

```java
// Before
public interface UserService {
    User getUser(String id);
    List<User> getUsers(int limit);
    User createUser(String name, String email);
}

// After
public interface UserService {
    Mono<User> getUser(String id);
    Flux<User> getUsers(int limit);
    Mono<User> createUser(String name, String email);
}
```

### Controller

```java
// Before (blocking)
@GetMapping("/users/{id}")
public ResponseEntity<User> getUser(@PathVariable String id) {
    User user = userService.getUser(id);
    return ResponseEntity.ok(user);
}

// After (reactive)
@GetMapping("/users/{id}")
public Mono<ResponseEntity<User>> getUser(@PathVariable String id) {
    return userService.getUser(id)
        .map(ResponseEntity::ok)
        .defaultIfEmpty(ResponseEntity.notFound().build());
}
```

### Composing Multiple Calls

```java
// Before — sequential, thread-blocking
User user = userService.getUser(id);
List<Order> orders = orderService.getOrdersForUser(id);
UserProfile profile = new UserProfile(user, orders);

// After — parallel, non-blocking
Mono<UserProfile> profile = Mono.zip(
    userService.getUser(id),
    orderService.getOrdersForUser(id).collectList()
).map(tuple -> new UserProfile(tuple.getT1(), tuple.getT2()));
```

## Stage 4: Add Resilience

```java
public Mono<User> getUser(String id) {
    return webClient.post()
        .bodyValue(Map.of(
            "query", "query($id: ID!) { user(id: $id) { id name email } }",
            "variables", Map.of("id", id)
        ))
        .retrieve()
        .bodyToMono(new ParameterizedTypeReference<GraphQLResponse<UserData>>() {})
        .timeout(Duration.ofSeconds(5))
        .retryWhen(Retry.backoff(3, Duration.ofSeconds(1))
            .filter(ex -> ex instanceof WebClientResponseException.ServiceUnavailable
                       || ex instanceof ConnectException))
        .map(response -> response.data().user())
        .onErrorMap(TimeoutException.class,
            ex -> new GraphQLException("Query timed out"))
        .onErrorMap(RetryExhaustedException.class,
            ex -> new GraphQLException("Service unavailable after retries", ex.getCause()));
}
```

## Handling Breaking Changes in DTOs

When the GraphQL schema changes during migration:

### Column/field rename

```java
// Old response
public record UserData(User user) {}
public record User(String id, String first_name, String last_name) {}

// New response — use @JsonAlias for backward compat during transition
public record User(
    String id,
    @JsonAlias("first_name") String firstName,
    @JsonAlias("last_name") String lastName
) {}
```

### Field added

```java
// Just add the field — Jackson ignores unknown by default
public record User(String id, String name, String email, String role) {}
```

### Field removed

```java
// Add @JsonIgnoreProperties to avoid failures on missing fields
@JsonIgnoreProperties(ignoreUnknown = true)
public record User(String id, String name) {}
```

## Checklist

- [ ] Identify all HttpClient GraphQL calls
- [ ] Add `spring-boot-starter-webflux` dependency
- [ ] Create WebClient bean with base URL and default headers
- [ ] Replace HttpClient calls with WebClient (one service at a time)
- [ ] Update return types to `Mono<T>` / `Flux<T>`
- [ ] Add timeout and retry policies
- [ ] Update tests to use `StepVerifier` or `MockWebServer`
- [ ] Remove HttpClient and manual ObjectMapper usage
- [ ] Consider upgrading to `HttpGraphQlClient` for cleaner API
