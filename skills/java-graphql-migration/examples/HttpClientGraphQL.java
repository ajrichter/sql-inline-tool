package com.example.graphql;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * Complete GraphQL client using java.net.http.HttpClient.
 * This is the "old way" — blocking, manual JSON handling.
 */
public class HttpClientGraphQL {

    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String graphqlUrl;
    private final String authToken;

    public HttpClientGraphQL(String graphqlUrl, String authToken) {
        this.graphqlUrl = graphqlUrl;
        this.authToken = authToken;
        this.objectMapper = new ObjectMapper();
        this.httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_2)
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    }

    // --- Core execute method ---

    public JsonNode execute(String query, Map<String, Object> variables)
            throws IOException, InterruptedException {

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("query", query);
        if (variables != null && !variables.isEmpty()) {
            requestBody.put("variables", variables);
        }

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(graphqlUrl))
            .header("Content-Type", "application/json")
            .header("Accept", "application/json")
            .header("Authorization", "Bearer " + authToken)
            .timeout(Duration.ofSeconds(30))
            .POST(HttpRequest.BodyPublishers.ofString(
                objectMapper.writeValueAsString(requestBody)))
            .build();

        HttpResponse<String> response = httpClient.send(
            request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new RuntimeException(
                "GraphQL HTTP error " + response.statusCode() + ": " + response.body());
        }

        JsonNode root = objectMapper.readTree(response.body());
        JsonNode errors = root.get("errors");
        if (errors != null && !errors.isNull() && errors.isArray() && !errors.isEmpty()) {
            throw new RuntimeException(
                "GraphQL error: " + errors.get(0).get("message").asText());
        }

        return root.get("data");
    }

    // --- Typed query method ---

    public <T> T query(String query, Map<String, Object> variables, Class<T> responseType)
            throws IOException, InterruptedException {

        JsonNode data = execute(query, variables);
        return objectMapper.treeToValue(data, responseType);
    }

    // --- Async variant ---

    public CompletableFuture<JsonNode> executeAsync(String query, Map<String, Object> variables) {
        try {
            Map<String, Object> requestBody = Map.of(
                "query", query,
                "variables", variables != null ? variables : Map.of()
            );

            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(graphqlUrl))
                .header("Content-Type", "application/json")
                .header("Authorization", "Bearer " + authToken)
                .POST(HttpRequest.BodyPublishers.ofString(
                    objectMapper.writeValueAsString(requestBody)))
                .build();

            return httpClient.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .thenApply(resp -> {
                    try {
                        return objectMapper.readTree(resp.body()).get("data");
                    } catch (IOException e) {
                        throw new RuntimeException("Failed to parse response", e);
                    }
                });
        } catch (IOException e) {
            return CompletableFuture.failedFuture(e);
        }
    }

    // --- Usage Examples ---

    public record User(String id, String name, String email) {}
    public record UserData(User user) {}
    public record UsersData(List<User> users) {}

    /** Get a single user by ID. */
    public User getUser(String id) throws IOException, InterruptedException {
        String query = """
            query GetUser($id: ID!) {
                user(id: $id) {
                    id
                    name
                    email
                }
            }
            """;

        JsonNode data = execute(query, Map.of("id", id));
        return objectMapper.treeToValue(data.get("user"), User.class);
    }

    /** List users with pagination. */
    public List<User> getUsers(int limit, int offset) throws IOException, InterruptedException {
        String query = """
            query GetUsers($limit: Int!, $offset: Int!) {
                users(limit: $limit, offset: $offset) {
                    id
                    name
                    email
                }
            }
            """;

        JsonNode data = execute(query, Map.of("limit", limit, "offset", offset));
        return objectMapper.readValue(
            data.get("users").toString(),
            new TypeReference<List<User>>() {}
        );
    }

    /** Create a new user. */
    public User createUser(String name, String email) throws IOException, InterruptedException {
        String mutation = """
            mutation CreateUser($input: CreateUserInput!) {
                createUser(input: $input) {
                    id
                    name
                    email
                }
            }
            """;

        Map<String, Object> variables = Map.of(
            "input", Map.of("name", name, "email", email)
        );

        JsonNode data = execute(mutation, variables);
        return objectMapper.treeToValue(data.get("createUser"), User.class);
    }

    // --- Main (demo) ---

    public static void main(String[] args) throws Exception {
        var client = new HttpClientGraphQL("https://api.example.com/graphql", "my-token");

        // Query
        User user = client.getUser("1");
        System.out.println("User: " + user.name());

        // Mutation
        User created = client.createUser("Bob", "bob@example.com");
        System.out.println("Created: " + created.id());

        // Async
        client.executeAsync(
            "{ users { id name } }", null
        ).thenAccept(data -> System.out.println("Async result: " + data));
    }
}
