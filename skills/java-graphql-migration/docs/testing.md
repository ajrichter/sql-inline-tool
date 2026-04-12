# Testing GraphQL Clients

## Dependencies

```xml
<dependency>
    <groupId>com.squareup.okhttp3</groupId>
    <artifactId>mockwebserver</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>io.projectreactor</groupId>
    <artifactId>reactor-test</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.wiremock</groupId>
    <artifactId>wiremock-standalone</artifactId>
    <scope>test</scope>
</dependency>
```

## MockWebServer (Recommended for WebClient)

### Setup

```java
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.MockResponse;

class GraphQLClientTest {

    private MockWebServer mockServer;
    private GraphQLService service;

    @BeforeEach
    void setUp() throws IOException {
        mockServer = new MockWebServer();
        mockServer.start();

        WebClient webClient = WebClient.create(
            mockServer.url("/graphql").toString());
        service = new GraphQLService(webClient);
    }

    @AfterEach
    void tearDown() throws IOException {
        mockServer.shutdown();
    }
}
```

### Testing a Successful Query

```java
@Test
void getUser_returnsUser() {
    mockServer.enqueue(new MockResponse()
        .setHeader("Content-Type", "application/json")
        .setBody("""
            {
                "data": {
                    "user": { "id": "1", "name": "Alice", "email": "alice@example.com" }
                }
            }
            """));

    StepVerifier.create(service.getUser("1"))
        .assertNext(user -> {
            assertThat(user.id()).isEqualTo("1");
            assertThat(user.name()).isEqualTo("Alice");
        })
        .verifyComplete();

    // Verify the request was correct
    RecordedRequest request = mockServer.takeRequest();
    assertThat(request.getMethod()).isEqualTo("POST");
    assertThat(request.getHeader("Content-Type")).contains("application/json");

    String requestBody = request.getBody().readUtf8();
    assertThat(requestBody).contains("GetUser");
    assertThat(requestBody).contains("\"id\":\"1\"");
}
```

### Testing GraphQL Errors

```java
@Test
void getUser_handlesGraphQLError() {
    mockServer.enqueue(new MockResponse()
        .setHeader("Content-Type", "application/json")
        .setBody("""
            {
                "data": null,
                "errors": [{
                    "message": "User not found",
                    "extensions": { "code": "NOT_FOUND" }
                }]
            }
            """));

    StepVerifier.create(service.getUser("999"))
        .expectError(GraphQLException.class)
        .verify();
}
```

### Testing HTTP Errors

```java
@Test
void getUser_handles500() {
    mockServer.enqueue(new MockResponse().setResponseCode(500));

    StepVerifier.create(service.getUser("1"))
        .expectError(GraphQLServerException.class)
        .verify();
}
```

### Testing Timeouts

```java
@Test
void getUser_handlesTimeout() {
    // Delay longer than the client timeout
    mockServer.enqueue(new MockResponse()
        .setHeader("Content-Type", "application/json")
        .setBody("{\"data\":{\"user\":{\"id\":\"1\"}}}")
        .setBodyDelay(15, TimeUnit.SECONDS));

    StepVerifier.create(service.getUser("1"))
        .expectError(TimeoutException.class)
        .verify();
}
```

### Testing Retries

```java
@Test
void getUser_retriesOnServerError() {
    // First two calls fail, third succeeds
    mockServer.enqueue(new MockResponse().setResponseCode(503));
    mockServer.enqueue(new MockResponse().setResponseCode(503));
    mockServer.enqueue(new MockResponse()
        .setHeader("Content-Type", "application/json")
        .setBody("""
            { "data": { "user": { "id": "1", "name": "Alice" } } }
            """));

    StepVerifier.create(service.getUser("1"))
        .assertNext(user -> assertThat(user.name()).isEqualTo("Alice"))
        .verifyComplete();

    assertThat(mockServer.getRequestCount()).isEqualTo(3);
}
```

## WireMock

### Setup with JUnit 5

```java
@WireMockTest(httpPort = 8089)
class GraphQLClientWireMockTest {

    private GraphQLService service;

    @BeforeEach
    void setUp() {
        WebClient webClient = WebClient.create("http://localhost:8089/graphql");
        service = new GraphQLService(webClient);
    }
}
```

### Request Matching

```java
@Test
void getUser_sendsCorrectQuery() {
    stubFor(post(urlEqualTo("/graphql"))
        .withHeader("Content-Type", containing("application/json"))
        .withRequestBody(matchingJsonPath("$.query", containing("GetUser")))
        .withRequestBody(matchingJsonPath("$.variables.id", equalTo("1")))
        .willReturn(aResponse()
            .withHeader("Content-Type", "application/json")
            .withBody("""
                { "data": { "user": { "id": "1", "name": "Alice" } } }
                """)));

    StepVerifier.create(service.getUser("1"))
        .assertNext(user -> assertThat(user.name()).isEqualTo("Alice"))
        .verifyComplete();

    verify(postRequestedFor(urlEqualTo("/graphql"))
        .withHeader("Content-Type", containing("application/json")));
}
```

## Testing HttpClient (Blocking)

For blocking HttpClient code, use standard JUnit assertions:

```java
@Test
void getUser_returnsUser() throws Exception {
    mockServer.enqueue(new MockResponse()
        .setHeader("Content-Type", "application/json")
        .setBody("""
            { "data": { "user": { "id": "1", "name": "Alice" } } }
            """));

    HttpClient httpClient = HttpClient.newHttpClient();
    GraphQLClient client = new GraphQLClient(
        mockServer.url("/graphql").toString(), httpClient);

    User user = client.getUser("1");
    assertThat(user.name()).isEqualTo("Alice");
}
```

## Integration Test with @SpringBootTest

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class GraphQLServiceIntegrationTest {

    @Autowired
    private GraphQLService service;

    @MockBean
    private WebClient webClient;

    @Test
    void contextLoads() {
        assertThat(service).isNotNull();
    }
}
```

## Test Utilities

### GraphQL Response Builder

```java
public class GraphQLTestHelper {

    public static String successResponse(String dataJson) {
        return """
            { "data": %s }
            """.formatted(dataJson);
    }

    public static String errorResponse(String message, String code) {
        return """
            {
                "data": null,
                "errors": [{
                    "message": "%s",
                    "extensions": { "code": "%s" }
                }]
            }
            """.formatted(message, code);
    }

    public static MockResponse jsonResponse(String body) {
        return new MockResponse()
            .setHeader("Content-Type", "application/json")
            .setBody(body);
    }
}
```
