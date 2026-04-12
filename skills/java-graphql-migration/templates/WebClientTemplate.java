package com.example.graphql;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

import java.net.ConnectException;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeoutException;

/**
 * Starter template: GraphQL client with Spring WebClient.
 *
 * Steps:
 * 1. Add spring-boot-starter-webflux to your pom.xml/build.gradle
 * 2. Set graphql.url and graphql.token in application.properties
 * 3. Add your DTOs and query methods following the patterns below
 *
 * application.properties:
 *   graphql.url=https://api.example.com/graphql
 *   graphql.token=your-token-here
 */

// --- Configuration (put in its own file or keep here) ---

@Configuration
class GraphQLClientConfig {

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

// --- Service ---

@Service
public class WebClientTemplate {

    private final WebClient webClient;

    public WebClientTemplate(WebClient graphqlWebClient) {
        this.webClient = graphqlWebClient;
    }

    // --- Response DTOs (shared across all queries) ---

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record GraphQLResponse<T>(T data, List<GraphQLError> errors) {
        boolean hasErrors() { return errors != null && !errors.isEmpty(); }
    }

    public record GraphQLError(String message, Map<String, Object> extensions) {}

    // --- Add your DTOs here ---

    // public record User(String id, String name, String email) {}
    // record UserData(User user) {}

    // --- Add your query methods here ---

    // public Mono<User> getUser(String id) {
    //     return execute(
    //         "query($id: ID!) { user(id: $id) { id name email } }",
    //         Map.of("id", id),
    //         new ParameterizedTypeReference<GraphQLResponse<UserData>>() {}
    //     ).map(UserData::user);
    // }

    // --- Core execution (don't modify) ---

    protected <T> Mono<T> execute(String query, Map<String, Object> variables,
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
                        "GraphQL: " + response.errors().get(0).message()));
                }
                return Mono.justOrEmpty(response.data());
            })
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
}
