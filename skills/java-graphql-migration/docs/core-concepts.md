# Core Concepts: GraphQL Over HTTP in Java

## How GraphQL Works Over HTTP

Unlike REST APIs with many endpoints, GraphQL uses a **single POST endpoint**. Every query, mutation, and subscription goes to the same URL (e.g., `/graphql`).

### Request Structure

```
POST /graphql HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>

{
  "query": "<GraphQL operation string>",
  "variables": { "<key>": "<value>" },
  "operationName": "<optional, for multi-operation documents>"
}
```

### Response Structure

GraphQL always returns HTTP 200, even on errors. The response body contains:

```json
{
  "data": { ... },
  "errors": [ { "message": "...", "locations": [...], "path": [...] } ]
}
```

**Partial responses** are valid — you can get both `data` and `errors` simultaneously.

## Query Types

### Query (read)

```graphql
query GetUser($id: ID!) {
  user(id: $id) {
    id
    name
    email
  }
}
```

### Mutation (write)

```graphql
mutation CreateUser($input: CreateUserInput!) {
  createUser(input: $input) {
    id
    name
  }
}
```

### Subscription (real-time, typically over WebSocket)

```graphql
subscription OnOrderUpdated($orderId: ID!) {
  orderUpdated(orderId: $orderId) {
    status
    updatedAt
  }
}
```

## Variables

Variables separate the query structure from its inputs. This enables:
- Query reuse
- Proper type checking
- Avoiding string interpolation (injection risk)

```java
// Always use variables for dynamic values
Map<String, Object> variables = Map.of(
    "id", userId,
    "limit", 10
);
Map<String, Object> requestBody = Map.of(
    "query", "query($id: ID!, $limit: Int) { user(id: $id) { orders(limit: $limit) { id } } }",
    "variables", variables
);
```

**Never** concatenate values into the query string:

```java
// BAD — injection risk, no type safety
String query = "{ user(id: \"" + userId + "\") { name } }";

// GOOD — use variables
String query = "query($id: ID!) { user(id: $id) { name } }";
Map<String, Object> variables = Map.of("id", userId);
```

## Fragments

Fragments let you reuse field selections:

```graphql
fragment UserFields on User {
  id
  name
  email
  createdAt
}

query {
  user(id: "1") { ...UserFields }
  admins { ...UserFields role }
}
```

In Java, store fragments as constants:

```java
public class Fragments {
    public static final String USER_FIELDS = """
        fragment UserFields on User {
            id
            name
            email
            createdAt
        }
        """;
}

// Compose queries
String query = Fragments.USER_FIELDS + """
    query GetUser($id: ID!) {
        user(id: $id) { ...UserFields }
    }
    """;
```

## Java Text Blocks

Java 15+ text blocks are ideal for GraphQL queries:

```java
String query = """
    query GetUsers($limit: Int, $offset: Int) {
        users(limit: $limit, offset: $offset) {
            id
            name
            email
            department {
                name
            }
        }
    }
    """;
```

## Response Deserialization

### With Jackson records (Java 16+)

```java
public record GraphQLResponse<T>(T data, List<GraphQLError> errors) {}
public record GraphQLError(String message, List<Object> path) {}
public record UserData(User user) {}
public record User(String id, String name, String email) {}

// Deserialize
GraphQLResponse<UserData> response = objectMapper.readValue(
    responseBody,
    new TypeReference<GraphQLResponse<UserData>>() {}
);
User user = response.data().user();
```

### With JsonNode (flexible)

```java
JsonNode root = objectMapper.readTree(responseBody);
JsonNode data = root.get("data");
JsonNode errors = root.get("errors");

if (errors != null && !errors.isNull()) {
    // Handle errors
}
String userName = data.get("user").get("name").asText();
```

## Operation Naming

Always name your operations for:
- Server-side logging and metrics
- Better error messages
- Multi-operation documents

```graphql
# Named — shows up in server logs as "GetUserProfile"
query GetUserProfile($id: ID!) {
  user(id: $id) { name }
}

# Anonymous — harder to debug
{
  user(id: "1") { name }
}
```

## Batching

Some GraphQL servers support query batching (sending an array of operations):

```java
List<Map<String, Object>> batch = List.of(
    Map.of("query", "{ user(id: \"1\") { name } }"),
    Map.of("query", "{ user(id: \"2\") { name } }")
);
String body = objectMapper.writeValueAsString(batch);
// Response will be a JSON array
```

**Note**: Not all servers support batching. Check your server's documentation.
