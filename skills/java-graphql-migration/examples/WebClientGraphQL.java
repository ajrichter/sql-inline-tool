package com.example.graphql;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ExchangeFilterFunction;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * Complete GraphQL client using Spring WebClient.
 * This is the "new way" — non-blocking, reactive, declarative error handling.
 */
public class WebClientGraphQL {

    private final WebClient webClient;

    public WebClientGraphQL(String graphqlUrl, String authToken) {
        this.webClient = WebClient.builder()
            .baseUrl(graphqlUrl)
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + authToken)
            .filter(logRequest())
            .build();
    }

    // Constructor for injecting a pre-configured WebClient (Spring bean)
    public WebClientGraphQL(WebClient webClient) {
        this.webClient = webClient;
    }

    // --- Response DTOs ---

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record GraphQLResponse<T>(T data, List<GraphQLError> errors) {
        public boolean hasErrors() {
            return errors != null && !errors.isEmpty();
        }
    }

    public record GraphQLError(
        String message,
        List<Object> path,
        Map<String, Object> extensions
    ) {}

    public record User(String id, String name, String email) {}
    public record UserData(User user) {}
    public record UsersData(List<User> users) {}
    public record CreateUserData(User createUser) {}

    // --- Core execute method ---

    public <T> Mono<T> execute(String query, Map<String, Object> variables,
                                ParameterizedTypeReference<GraphQLResponse<T>> typeRef) {

        Map<String, Object> requestBody = variables != null && !variables.isEmpty()
            ? Map.of("query", query, "variables", variables)
            : Map.of("query", query);

        return webClient.post()
            .bodyValue(requestBody)
            .retrieve()
            .onStatus(HttpStatusCode::is4xxClientError, response ->
                response.bodyToMono(String.class)
                    .flatMap(body -> Mono.error(new RuntimeException("Client error: " + body))))
            .onStatus(HttpStatusCode::is5xxServerError, response ->
                Mono.error(new RuntimeException("Server error")))
            .bodyToMono(typeRef)
            .flatMap(response -> {
                if (response.hasErrors() && response.data() == null) {
                    return Mono.error(new RuntimeException(
                        "GraphQL error: " + response.errors().get(0).message()));
                }
                return Mono.justOrEmpty(response.data());
            })
            .timeout(Duration.ofSeconds(10))
            .retryWhen(Retry.backoff(3, Duration.ofSeconds(1))
                .filter(this::isRetryable));
    }

    // --- Query methods ---

    /** Get a single user by ID. */
    public Mono<User> getUser(String id) {
        String query = """
            query GetUser($id: ID!) {
                user(id: $id) {
                    id
                    name
                    email
                }
            }
            """;

        return execute(
            query,
            Map.of("id", id),
            new ParameterizedTypeReference<GraphQLResponse<UserData>>() {}
        ).map(UserData::user);
    }

    /** List users with pagination. */
    public Flux<User> getUsers(int limit, int offset) {
        String query = """
            query GetUsers($limit: Int!, $offset: Int!) {
                users(limit: $limit, offset: $offset) {
                    id
                    name
                    email
                }
            }
            """;

        return execute(
            query,
            Map.of("limit", limit, "offset", offset),
            new ParameterizedTypeReference<GraphQLResponse<UsersData>>() {}
        ).flatMapMany(data -> Flux.fromIterable(data.users()));
    }

    /** Create a new user (mutation). */
    public Mono<User> createUser(String name, String email) {
        String mutation = """
            mutation CreateUser($input: CreateUserInput!) {
                createUser(input: $input) {
                    id
                    name
                    email
                }
            }
            """;

        return execute(
            mutation,
            Map.of("input", Map.of("name", name, "email", email)),
            new ParameterizedTypeReference<GraphQLResponse<CreateUserData>>() {}
        ).map(CreateUserData::createUser);
    }

    // --- Parallel queries ---

    /** Fetch user and their orders in parallel. */
    public Mono<Map<String, Object>> getUserWithOrders(String userId) {
        Mono<User> userMono = getUser(userId);
        Mono<List<User>> friendsMono = getUsers(10, 0).collectList();

        return Mono.zip(userMono, friendsMono)
            .map(tuple -> Map.of(
                "user", tuple.getT1(),
                "friends", tuple.getT2()
            ));
    }

    // --- Blocking bridge (for non-reactive callers) ---

    public User getUserBlocking(String id) {
        return getUser(id).block(Duration.ofSeconds(15));
    }

    // --- Helpers ---

    private boolean isRetryable(Throwable ex) {
        if (ex instanceof WebClientResponseException wcre) {
            return wcre.getStatusCode().is5xxServerError();
        }
        return ex instanceof java.net.ConnectException
            || ex instanceof java.util.concurrent.TimeoutException;
    }

    private static ExchangeFilterFunction logRequest() {
        return ExchangeFilterFunction.ofRequestProcessor(request -> {
            System.out.printf("GraphQL %s %s%n", request.method(), request.url());
            return Mono.just(request);
        });
    }

    // --- Main (demo) ---

    public static void main(String[] args) {
        var client = new WebClientGraphQL(
            "https://api.example.com/graphql", "my-token");

        // Reactive
        client.getUser("1")
            .subscribe(user -> System.out.println("User: " + user.name()));

        // Blocking bridge
        User user = client.getUserBlocking("1");
        System.out.println("Blocking: " + user.name());

        // Parallel
        client.getUserWithOrders("1")
            .subscribe(result -> System.out.println("Result: " + result));
    }
}
