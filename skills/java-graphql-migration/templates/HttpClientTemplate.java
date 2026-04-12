package com.example.graphql;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Map;

/**
 * Starter template: GraphQL client with java.net.http.HttpClient.
 *
 * Steps:
 * 1. Set GRAPHQL_URL and AUTH_TOKEN
 * 2. Add your query/mutation methods following the getExample() pattern
 * 3. Map response JSON to your DTOs
 */
public class HttpClientTemplate {

    private static final String GRAPHQL_URL = "https://api.example.com/graphql";
    private static final String AUTH_TOKEN = "your-token-here";

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    public HttpClientTemplate() {
        this.objectMapper = new ObjectMapper();
        this.httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_2)
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    }

    // --- Add your DTOs here ---

    // public record User(String id, String name, String email) {}

    // --- Add your query methods here ---

    // public User getUser(String id) throws IOException, InterruptedException {
    //     JsonNode data = execute(
    //         "query($id: ID!) { user(id: $id) { id name email } }",
    //         Map.of("id", id)
    //     );
    //     return objectMapper.treeToValue(data.get("user"), User.class);
    // }

    // --- Core execution (don't modify) ---

    protected JsonNode execute(String query, Map<String, Object> variables)
            throws IOException, InterruptedException {

        String body = objectMapper.writeValueAsString(
            variables != null
                ? Map.of("query", query, "variables", variables)
                : Map.of("query", query));

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(GRAPHQL_URL))
            .header("Content-Type", "application/json")
            .header("Accept", "application/json")
            .header("Authorization", "Bearer " + AUTH_TOKEN)
            .timeout(Duration.ofSeconds(30))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();

        HttpResponse<String> response = httpClient.send(
            request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new RuntimeException("HTTP " + response.statusCode() + ": " + response.body());
        }

        JsonNode root = objectMapper.readTree(response.body());
        JsonNode errors = root.get("errors");
        if (errors != null && !errors.isNull() && errors.isArray() && !errors.isEmpty()) {
            throw new RuntimeException("GraphQL: " + errors.get(0).get("message").asText());
        }

        return root.get("data");
    }

    // --- Example usage ---

    public JsonNode getExample() throws IOException, InterruptedException {
        return execute("{ __schema { types { name } } }", null);
    }

    public static void main(String[] args) throws Exception {
        var client = new HttpClientTemplate();
        System.out.println(client.getExample());
    }
}
