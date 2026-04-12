package com.example.graphql.migration;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * BEFORE migration: GraphQL service using java.net.http.HttpClient.
 *
 * Problems:
 * - Blocking — ties up a thread per request
 * - Manual JSON serialization/deserialization
 * - Manual retry logic
 * - No connection pooling configuration
 * - Verbose error handling
 *
 * Compare with MigrationAfter.java for the WebClient version.
 */
public class MigrationBefore {

    // --- DTOs ---
    public record User(String id, String name, String email, String departmentId) {}
    public record Order(String id, String status, double total) {}
    public record UserProfile(User user, List<Order> orders) {}

    // --- Service ---
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String graphqlUrl;
    private final String authToken;

    public MigrationBefore(String graphqlUrl, String authToken) {
        this.graphqlUrl = graphqlUrl;
        this.authToken = authToken;
        this.objectMapper = new ObjectMapper();
        this.httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    }

    // --- Queries ---

    public User getUser(String id) throws IOException, InterruptedException {
        String query = """
            query GetUser($id: ID!) {
                user(id: $id) { id name email departmentId }
            }
            """;

        JsonNode data = executeWithRetry(query, Map.of("id", id), 3);
        return objectMapper.treeToValue(data.get("user"), User.class);
    }

    public List<Order> getOrdersForUser(String userId)
            throws IOException, InterruptedException {

        String query = """
            query GetOrders($userId: ID!) {
                orders(userId: $userId) { id status total }
            }
            """;

        JsonNode data = executeWithRetry(query, Map.of("userId", userId), 3);
        return objectMapper.readValue(
            data.get("orders").toString(),
            new TypeReference<List<Order>>() {}
        );
    }

    /**
     * Get user profile — fetches user and orders SEQUENTIALLY.
     * This blocks the thread twice.
     */
    public UserProfile getUserProfile(String userId)
            throws IOException, InterruptedException {

        User user = getUser(userId);                    // blocks
        List<Order> orders = getOrdersForUser(userId);  // blocks again
        return new UserProfile(user, orders);
    }

    // --- Core execution ---

    private JsonNode execute(String query, Map<String, Object> variables)
            throws IOException, InterruptedException {

        String body = objectMapper.writeValueAsString(
            Map.of("query", query, "variables", variables));

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(graphqlUrl))
            .header("Content-Type", "application/json")
            .header("Authorization", "Bearer " + authToken)
            .timeout(Duration.ofSeconds(30))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();

        HttpResponse<String> response = httpClient.send(
            request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new RuntimeException("HTTP " + response.statusCode());
        }

        JsonNode root = objectMapper.readTree(response.body());
        JsonNode errors = root.get("errors");
        if (errors != null && !errors.isNull() && !errors.isEmpty()) {
            throw new RuntimeException("GraphQL: " + errors.get(0).get("message").asText());
        }

        return root.get("data");
    }

    /** Manual retry with exponential backoff — this is what WebClient replaces. */
    private JsonNode executeWithRetry(String query, Map<String, Object> variables, int maxRetries)
            throws IOException, InterruptedException {

        int attempt = 0;
        while (true) {
            try {
                return execute(query, variables);
            } catch (IOException | RuntimeException e) {
                if (++attempt >= maxRetries) {
                    throw e;
                }
                Thread.sleep((long) Math.pow(2, attempt) * 1000);
            }
        }
    }
}
