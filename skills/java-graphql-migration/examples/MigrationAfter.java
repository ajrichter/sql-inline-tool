package com.example.graphql.migration;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

import java.net.ConnectException;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeoutException;

/**
 * AFTER migration: Same GraphQL service using Spring WebClient.
 *
 * Improvements over MigrationBefore.java:
 * - Non-blocking — no threads tied up waiting
 * - Declarative retry with backoff (no manual loops)
 * - Parallel queries with Mono.zip
 * - Built-in connection pooling via Netty
 * - Clean error handling with onStatus/onErrorMap
 * - Spring-managed bean lifecycle
 *
 * Compare with MigrationBefore.java for the HttpClient version.
 */
@Service
public class MigrationAfter {

    // --- DTOs (same as before — no change needed) ---

    public record User(String id, String name, String email, String departmentId) {}
    public record Order(String id, String status, double total) {}
    public record UserProfile(User user, List<Order> orders) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record GraphQLResponse<T>(T data, List<GraphQLError> errors) {
        boolean hasErrors() { return errors != null && !errors.isEmpty(); }
    }
    public record GraphQLError(String message, Map<String, Object> extensions) {}

    // Wrapper types for response deserialization
    record UserData(User user) {}
    record OrdersData(List<Order> orders) {}

    // --- Service ---

    private final WebClient webClient;

    public MigrationAfter(WebClient.Builder webClientBuilder,
                          String graphqlUrl, String authToken) {
        this.webClient = webClientBuilder
            .baseUrl(graphqlUrl)
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + authToken)
            .build();
    }

    // --- Queries ---

    public Mono<User> getUser(String id) {
        String query = """
            query GetUser($id: ID!) {
                user(id: $id) { id name email departmentId }
            }
            """;

        return execute(query, Map.of("id", id),
            new ParameterizedTypeReference<GraphQLResponse<UserData>>() {})
            .map(UserData::user);
    }

    public Flux<Order> getOrdersForUser(String userId) {
        String query = """
            query GetOrders($userId: ID!) {
                orders(userId: $userId) { id status total }
            }
            """;

        return execute(query, Map.of("userId", userId),
            new ParameterizedTypeReference<GraphQLResponse<OrdersData>>() {})
            .flatMapMany(data -> Flux.fromIterable(data.orders()));
    }

    /**
     * Get user profile — fetches user and orders IN PARALLEL.
     * Compare with MigrationBefore.getUserProfile() which blocks twice sequentially.
     */
    public Mono<UserProfile> getUserProfile(String userId) {
        Mono<User> userMono = getUser(userId);
        Mono<List<Order>> ordersMono = getOrdersForUser(userId).collectList();

        return Mono.zip(userMono, ordersMono)
            .map(tuple -> new UserProfile(tuple.getT1(), tuple.getT2()));
    }

    // --- Core execution (replaces execute + executeWithRetry) ---

    private <T> Mono<T> execute(String query, Map<String, Object> variables,
                                 ParameterizedTypeReference<GraphQLResponse<T>> typeRef) {

        return webClient.post()
            .bodyValue(Map.of("query", query, "variables", variables))
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
                        "GraphQL: " + response.errors().get(0).message()));
                }
                return Mono.justOrEmpty(response.data());
            })
            // Replaces manual Thread.sleep retry loop
            .timeout(Duration.ofSeconds(10))
            .retryWhen(Retry.backoff(3, Duration.ofSeconds(1))
                .filter(this::isRetryable));
    }

    private boolean isRetryable(Throwable ex) {
        if (ex instanceof WebClientResponseException wcre) {
            return wcre.getStatusCode().is5xxServerError();
        }
        return ex instanceof ConnectException || ex instanceof TimeoutException;
    }

    // --- Blocking bridge (for gradual migration of callers) ---

    /** Use this to keep old calling code working while you migrate callers. */
    public User getUserBlocking(String id) {
        return getUser(id).block(Duration.ofSeconds(15));
    }

    public UserProfile getUserProfileBlocking(String userId) {
        return getUserProfile(userId).block(Duration.ofSeconds(15));
    }
}
