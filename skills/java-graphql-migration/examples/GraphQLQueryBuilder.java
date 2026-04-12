package com.example.graphql;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Type-safe GraphQL query builder for Java.
 * Avoids string concatenation and provides a fluent API.
 *
 * Usage:
 *   var request = GraphQLQueryBuilder.query("GetUser")
 *       .variable("id", "ID!", userId)
 *       .field("user(id: $id)", f -> f
 *           .field("id")
 *           .field("name")
 *           .field("email")
 *           .field("department", d -> d
 *               .field("name")
 *               .field("code")))
 *       .build();
 *
 *   // request.query()     → "query GetUser($id: ID!) { user(id: $id) { id name email department { name code } } }"
 *   // request.variables() → {"id": userId}
 *   // request.toBody()    → {"query": "...", "variables": {...}}
 */
public class GraphQLQueryBuilder {

    public record GraphQLRequest(String query, Map<String, Object> variables) {
        public Map<String, Object> toBody() {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("query", query);
            if (variables != null && !variables.isEmpty()) {
                body.put("variables", variables);
            }
            return body;
        }
    }

    private final String operationType; // "query" or "mutation"
    private final String operationName;
    private final List<VariableDef> variableDefs = new ArrayList<>();
    private final Map<String, Object> variableValues = new LinkedHashMap<>();
    private final FieldBuilder rootFields = new FieldBuilder();

    private record VariableDef(String name, String type) {}

    private GraphQLQueryBuilder(String operationType, String operationName) {
        this.operationType = operationType;
        this.operationName = operationName;
    }

    public static GraphQLQueryBuilder query(String operationName) {
        return new GraphQLQueryBuilder("query", operationName);
    }

    public static GraphQLQueryBuilder mutation(String operationName) {
        return new GraphQLQueryBuilder("mutation", operationName);
    }

    /** Declare a variable with its GraphQL type and value. */
    public GraphQLQueryBuilder variable(String name, String graphqlType, Object value) {
        variableDefs.add(new VariableDef(name, graphqlType));
        variableValues.put(name, value);
        return this;
    }

    /** Add a scalar field. */
    public GraphQLQueryBuilder field(String fieldName) {
        rootFields.field(fieldName);
        return this;
    }

    /** Add a field with nested sub-fields. */
    public GraphQLQueryBuilder field(String fieldName, java.util.function.Consumer<FieldBuilder> nested) {
        rootFields.field(fieldName, nested);
        return this;
    }

    /** Add a fragment spread. */
    public GraphQLQueryBuilder fragment(String fragmentName) {
        rootFields.fragment(fragmentName);
        return this;
    }

    /** Build the final query string and variables map. */
    public GraphQLRequest build() {
        StringBuilder sb = new StringBuilder();
        sb.append(operationType);

        if (operationName != null) {
            sb.append(" ").append(operationName);
        }

        if (!variableDefs.isEmpty()) {
            String vars = variableDefs.stream()
                .map(v -> "$" + v.name + ": " + v.type)
                .collect(Collectors.joining(", "));
            sb.append("(").append(vars).append(")");
        }

        sb.append(" ").append(rootFields.build());

        return new GraphQLRequest(sb.toString(), variableValues);
    }

    // --- FieldBuilder for nested selections ---

    public static class FieldBuilder {
        private final List<String> entries = new ArrayList<>();

        public FieldBuilder field(String fieldName) {
            entries.add(fieldName);
            return this;
        }

        public FieldBuilder field(String fieldName, java.util.function.Consumer<FieldBuilder> nested) {
            FieldBuilder sub = new FieldBuilder();
            nested.accept(sub);
            entries.add(fieldName + " " + sub.build());
            return this;
        }

        public FieldBuilder fragment(String fragmentName) {
            entries.add("..." + fragmentName);
            return this;
        }

        String build() {
            return "{ " + String.join(" ", entries) + " }";
        }
    }

    // --- Demo ---

    public static void main(String[] args) {
        // Query example
        var getUserRequest = GraphQLQueryBuilder.query("GetUser")
            .variable("id", "ID!", "user-123")
            .field("user(id: $id)", f -> f
                .field("id")
                .field("name")
                .field("email")
                .field("department", d -> d
                    .field("name")
                    .field("code")))
            .build();

        System.out.println("Query: " + getUserRequest.query());
        System.out.println("Variables: " + getUserRequest.variables());
        System.out.println("Body: " + getUserRequest.toBody());

        // Mutation example
        var createUserRequest = GraphQLQueryBuilder.mutation("CreateUser")
            .variable("input", "CreateUserInput!", Map.of("name", "Alice", "email", "alice@example.com"))
            .field("createUser(input: $input)", f -> f
                .field("id")
                .field("name"))
            .build();

        System.out.println("\nMutation: " + createUserRequest.query());
        System.out.println("Variables: " + createUserRequest.variables());
    }
}
