# Spring WebClient for GraphQL

Spring WebClient is a non-blocking, reactive HTTP client built on Project Reactor. It's the recommended replacement for RestTemplate and the ideal transport for GraphQL in Spring applications.

## Basic Setup

### As a Spring Bean

```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class GraphQLConfig {

    @Bean
    public WebClient graphqlWebClient(
            @Value("${graphql.url}") String graphqlUrl,
            @Value("${graphql.token}") String token) {

        return WebClient.builder()
            .baseUrl(graphqlUrl)
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + token)
            .build();
    }
}
```

### Standalone

```java
WebClient webClient = WebClient.builder()
    .baseUrl("https://api.example.com/graphql")
    .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
    .build();
```

## Sending Queries

### Returning a Mono (reactive)

```java
public Mono<GraphQLResponse<UserData>> getUser(String id) {
    return webClient.post()
        .bodyValue(Map.of(
            "query", "query($id: ID!) { user(id: $id) { id name email } }",
            "variables", Map.of("id", id)
        ))
        .retrieve()
        .bodyToMono(new ParameterizedTypeReference<GraphQLResponse<UserData>>() {});
}
```

### Blocking (for non-reactive callers)

```java
public User getUserBlocking(String id) {
    return getUser(id)
        .map(resp -> resp.data().user())
        .block(Duration.ofSeconds(10));
}
```

### Multiple Queries in Parallel

```java
public Mono<Tuple2<User, List<Order>>> getUserWithOrders(String userId) {
    Mono<User> userMono = getUser(userId).map(r -> r.data().user());
    Mono<List<Order>> ordersMono = getOrders(userId).map(r -> r.data().orders());

    return Mono.zip(userMono, ordersMono);
}
```

## Mutations

```java
public Mono<GraphQLResponse<CreateUserData>> createUser(String name, String email) {
    return webClient.post()
        .bodyValue(Map.of(
            "query", """
                mutation($input: CreateUserInput!) {
                    createUser(input: $input) { id name email }
                }
                """,
            "variables", Map.of("input", Map.of("name", name, "email", email))
        ))
        .retrieve()
        .bodyToMono(new ParameterizedTypeReference<GraphQLResponse<CreateUserData>>() {});
}
```

## Error Handling

### HTTP-level errors

```java
webClient.post()
    .bodyValue(requestBody)
    .retrieve()
    .onStatus(HttpStatusCode::is4xxClientError, response ->
        response.bodyToMono(String.class)
            .flatMap(body -> Mono.error(new GraphQLClientException(body))))
    .onStatus(HttpStatusCode::is5xxServerError, response ->
        Mono.error(new GraphQLServerException("Server error")))
    .bodyToMono(GraphQLResponse.class);
```

### GraphQL-level errors (in the response body)

```java
public Mono<User> getUserOrError(String id) {
    return getUser(id)
        .flatMap(response -> {
            if (response.errors() != null && !response.errors().isEmpty()) {
                String msg = response.errors().get(0).message();
                return Mono.error(new GraphQLException(msg));
            }
            return Mono.justOrEmpty(response.data().user());
        });
}
```

## Retry and Timeout

```java
webClient.post()
    .bodyValue(requestBody)
    .retrieve()
    .bodyToMono(GraphQLResponse.class)
    .timeout(Duration.ofSeconds(10))
    .retryWhen(Retry.backoff(3, Duration.ofSeconds(1))
        .maxBackoff(Duration.ofSeconds(10))
        .filter(this::isRetryable)
        .onRetryExhaustedThrow((spec, signal) ->
            new GraphQLException("Retries exhausted", signal.failure())));

private boolean isRetryable(Throwable ex) {
    if (ex instanceof WebClientResponseException wcre) {
        return wcre.getStatusCode().is5xxServerError();
    }
    return ex instanceof java.net.ConnectException
        || ex instanceof java.util.concurrent.TimeoutException;
}
```

## Request/Response Logging

```java
WebClient webClient = WebClient.builder()
    .baseUrl(graphqlUrl)
    .filter(logRequest())
    .filter(logResponse())
    .build();

private ExchangeFilterFunction logRequest() {
    return ExchangeFilterFunction.ofRequestProcessor(request -> {
        log.debug("GraphQL {} {}", request.method(), request.url());
        return Mono.just(request);
    });
}

private ExchangeFilterFunction logResponse() {
    return ExchangeFilterFunction.ofResponseProcessor(response -> {
        log.debug("GraphQL response: {}", response.statusCode());
        return Mono.just(response);
    });
}
```

## Connection Pool Tuning

```java
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

ConnectionProvider provider = ConnectionProvider.builder("graphql-pool")
    .maxConnections(50)
    .maxIdleTime(Duration.ofSeconds(20))
    .maxLifeTime(Duration.ofMinutes(5))
    .pendingAcquireTimeout(Duration.ofSeconds(10))
    .evictInBackground(Duration.ofSeconds(30))
    .build();

HttpClient nettyClient = HttpClient.create(provider)
    .responseTimeout(Duration.ofSeconds(10))
    .compress(true);

WebClient webClient = WebClient.builder()
    .baseUrl(graphqlUrl)
    .clientConnector(new ReactorClientHttpConnector(nettyClient))
    .build();
```

## Using HttpGraphQlClient (Spring GraphQL)

Spring Boot 3.x provides `HttpGraphQlClient` which wraps WebClient with first-class GraphQL support:

```java
@Bean
public HttpGraphQlClient graphQlClient(WebClient graphqlWebClient) {
    return HttpGraphQlClient.builder(graphqlWebClient).build();
}

// Usage — much cleaner than raw WebClient
public Mono<User> getUser(String id) {
    return graphQlClient
        .document("query($id: ID!) { user(id: $id) { id name email } }")
        .variable("id", id)
        .retrieve("user")
        .toEntity(User.class);
}

// Mutations
public Mono<User> createUser(String name, String email) {
    return graphQlClient
        .document("""
            mutation($input: CreateUserInput!) {
                createUser(input: $input) { id name }
            }
            """)
        .variable("input", Map.of("name", name, "email", email))
        .retrieve("createUser")
        .toEntity(User.class);
}

// Lists
public Flux<User> getUsers() {
    return graphQlClient
        .document("{ users { id name email } }")
        .retrieve("users")
        .toEntityList(User.class)
        .flatMapMany(Flux::fromIterable);
}
```

## WebClient vs HttpGraphQlClient

| Feature | Raw WebClient | HttpGraphQlClient |
|---------|--------------|-------------------|
| JSON serialization | Manual (Map → body) | Automatic |
| Variable binding | Manual Map | `.variable("key", value)` |
| Response extraction | Full response deserialization | `.retrieve("path").toEntity()` |
| Error handling | Manual JSON parsing | Built-in GraphQL error support |
| Subscriptions | Not supported | `.retrieveSubscription()` |
| Setup complexity | Low | Requires spring-boot-starter-graphql |

Use raw WebClient when you want full control or can't add the GraphQL starter. Use HttpGraphQlClient for the cleanest API.
