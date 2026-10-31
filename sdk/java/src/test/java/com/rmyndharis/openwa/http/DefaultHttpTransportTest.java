package com.rmyndharis.openwa.http;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.rmyndharis.openwa.ClientConfig;
import com.rmyndharis.openwa.OpenWAClient;
import com.rmyndharis.openwa.errors.OpenWAApiError;
import com.rmyndharis.openwa.errors.OpenWATimeoutError;
import com.sun.net.httpserver.HttpServer;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.Authenticator;
import java.net.CookieHandler;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ProxySelector;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLParameters;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

/** Runs the real transport against a local server: no client test covers it otherwise. */
class DefaultHttpTransportTest {
    private HttpServer server;
    private String baseUrl;
    private final CountDownLatch release = new CountDownLatch(1);

    @BeforeEach
    void start() throws Exception {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.start();
        baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
    }

    @AfterEach
    void stop() {
        release.countDown();
        server.stop(0);
    }

    private OpenWAClient client(Duration timeout) {
        return new OpenWAClient(ClientConfig.builder().baseUrl(baseUrl).apiKey("owa_k1_x").timeout(timeout).build());
    }

    @Test
    void neverFollowsARedirect() {
        AtomicReference<String> keySeen = new AtomicReference<>();
        AtomicInteger targetHits = new AtomicInteger();
        server.createContext("/a", ex -> {
            keySeen.set(ex.getRequestHeaders().getFirst("X-API-Key"));
            ex.getResponseHeaders().add("Location", baseUrl + "/b");
            ex.sendResponseHeaders(302, -1);
            ex.close();
        });
        server.createContext("/b", ex -> {
            targetHits.incrementAndGet();
            ex.sendResponseHeaders(204, -1);
            ex.close();
        });

        OpenWAApiError err = assertThrows(OpenWAApiError.class,
            () -> client(Duration.ofSeconds(5)).requestVoid(HttpMethod.GET, "/a", null, null));

        assertEquals(302, err.status());
        assertEquals("owa_k1_x", keySeen.get());
        assertEquals(0, targetHits.get());
    }

    @Test
    void mapsATimeoutToOpenWATimeoutError() {
        server.createContext("/slow", ex -> {
            try {
                Thread.sleep(1000);
                ex.sendResponseHeaders(204, -1);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                ex.close();
            }
        });

        assertThrows(OpenWATimeoutError.class,
            () -> client(Duration.ofMillis(100)).requestVoid(HttpMethod.GET, "/slow", null, null));
    }

    @Test
    @Timeout(30)
    void mapsABodyStallToOpenWATimeoutErrorAndDropsTheConnection() throws Exception {
        CountDownLatch started = new CountDownLatch(1);
        CountDownLatch clientClosed = new CountDownLatch(1);
        server.createContext("/stall", ex -> {
            try {
                // A body that never ends: keeps writing until the client hangs up.
                ex.sendResponseHeaders(200, 0);
                started.countDown();
                while (!release.await(20, TimeUnit.MILLISECONDS)) {
                    ex.getResponseBody().write(' ');
                    ex.getResponseBody().flush();
                }
            } catch (IOException e) {
                clientClosed.countDown();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                ex.close();
            }
        });

        // The budget covers connecting and a fresh client's first use as well, so a starved machine
        // needs more than the 100 ms of the header-timeout test; the server stalls for as long as it takes.
        assertThrows(OpenWATimeoutError.class,
            () -> client(Duration.ofMillis(1500)).requestVoid(HttpMethod.GET, "/stall", null, null));
        assertTrue(started.await(5, TimeUnit.SECONDS), "the stalled exchange never reached the server");
        assertTrue(clientClosed.await(5, TimeUnit.SECONDS), "the timed-out exchange was not cancelled");
    }

    @Test
    void reportsAFailedExchangeAsAnIOException() {
        // HttpClient fails an exchange it cannot schedule (a deadline that overflows, a closed selector
        // manager) with a runtime exception, and it must not escape the transport as one. The failure is
        // injected: which exchanges a JDK fails that way differs between releases.
        RecordingClient failing = new RecordingClient(new ArithmeticException("long overflow"));
        HttpRequestData req = new HttpRequestData(
            HttpMethod.GET, baseUrl + "/ok", Map.of(), null, Duration.ofSeconds(5));

        IOException err = assertThrows(IOException.class, () -> new DefaultHttpTransport(failing).send(req));

        assertInstanceOf(ArithmeticException.class, err.getCause());
        assertEquals(1, failing.started.get());
    }

    /** A client that records the exchanges it is asked to start, and fails them when given a failure. */
    private static final class RecordingClient extends HttpClient {
        final AtomicInteger started = new AtomicInteger();
        private final Throwable failure;

        RecordingClient() {
            this(null);
        }

        RecordingClient(Throwable failure) {
            this.failure = failure;
        }

        @Override public Optional<CookieHandler> cookieHandler() { return Optional.empty(); }
        @Override public Optional<Duration> connectTimeout() { return Optional.empty(); }
        @Override public Redirect followRedirects() { return Redirect.NEVER; }
        @Override public Optional<ProxySelector> proxy() { return Optional.empty(); }
        @Override public SSLContext sslContext() { throw new UnsupportedOperationException(); }
        @Override public SSLParameters sslParameters() { throw new UnsupportedOperationException(); }
        @Override public Optional<Authenticator> authenticator() { return Optional.empty(); }
        @Override public Version version() { return Version.HTTP_1_1; }
        @Override public Optional<Executor> executor() { return Optional.empty(); }

        @Override
        public <T> HttpResponse<T> send(HttpRequest request, HttpResponse.BodyHandler<T> handler) {
            throw new UnsupportedOperationException();
        }

        @Override
        public <T> CompletableFuture<HttpResponse<T>> sendAsync(
            HttpRequest request, HttpResponse.BodyHandler<T> handler) {
            started.incrementAndGet();
            return failure == null ? new CompletableFuture<>() : CompletableFuture.failedFuture(failure);
        }

        @Override
        public <T> CompletableFuture<HttpResponse<T>> sendAsync(
            HttpRequest request, HttpResponse.BodyHandler<T> handler, HttpResponse.PushPromiseHandler<T> push) {
            return sendAsync(request, handler);
        }
    }

    @Test
    void aCallerThatIsAlreadyInterruptedStartsNoExchange() {
        // HttpClient.send refuses before dispatching anything when the thread's interrupt flag is set;
        // starting the exchange first could still deliver a request the caller is told was interrupted.
        RecordingClient recording = new RecordingClient();
        HttpRequestData req = new HttpRequestData(
            HttpMethod.GET, baseUrl + "/ok", Map.of(), null, Duration.ofSeconds(5));
        Thread.currentThread().interrupt();
        try {
            assertThrows(InterruptedException.class, () -> new DefaultHttpTransport(recording).send(req));
        } finally {
            Thread.interrupted();
        }
        assertEquals(0, recording.started.get());
    }

    @Test
    @Timeout(30)
    void speaksHttp1ToAServerThatAnswersNothingToAnH2cUpgrade() throws Exception {
        // The gateway's HTTP server hands a request that asks to upgrade to Socket.IO, which answers
        // nothing when the path is not its own. The JDK client asks for h2c on a cleartext connection
        // unless it is pinned to HTTP/1.1, and com.sun.net.httpserver ignores the header, so only a
        // raw socket reproduces the server.
        try (ServerSocket raw = new ServerSocket(0, 50, InetAddress.getByName("127.0.0.1"))) {
            Thread serving = new Thread(() -> {
                try {
                    while (true) {
                        try (Socket socket = raw.accept()) {
                            String head = readHead(socket.getInputStream()).toLowerCase(Locale.ROOT);
                            if (!head.contains("upgrade: h2c")) {
                                socket.getOutputStream().write((
                                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                                        + "Content-Length: 2\r\nConnection: close\r\n\r\n{}")
                                    .getBytes(StandardCharsets.US_ASCII));
                            }
                        }
                    }
                } catch (IOException closed) {
                    // the test ended
                }
            });
            serving.setDaemon(true);
            serving.start();
            OpenWAClient plain = new OpenWAClient(ClientConfig.builder()
                .baseUrl("http://127.0.0.1:" + raw.getLocalPort())
                .apiKey("owa_k1_x")
                .timeout(Duration.ofSeconds(5))
                .build());

            assertDoesNotThrow(() -> plain.requestVoid(HttpMethod.GET, "/api/health", null, null));
        }
    }

    private static String readHead(InputStream in) throws IOException {
        ByteArrayOutputStream head = new ByteArrayOutputStream();
        int last4 = 0;
        int b;
        while ((b = in.read()) != -1) {
            head.write(b);
            last4 = (last4 << 8) | b;
            if (last4 == 0x0d0a0d0a) {
                break;
            }
        }
        return head.toString(StandardCharsets.US_ASCII);
    }

    @Test
    void passesThroughOnlyTheFailuresHttpClientSendDoes() {
        IOException io = new IOException("reset");
        assertSame(io, DefaultHttpTransport.transportFailure(io));

        IllegalArgumentException bad = new IllegalArgumentException("bad header");
        assertSame(bad, assertThrows(IllegalArgumentException.class, () -> DefaultHttpTransport.transportFailure(bad)));
        SecurityException denied = new SecurityException("denied");
        assertSame(denied, assertThrows(SecurityException.class, () -> DefaultHttpTransport.transportFailure(denied)));

        IllegalStateException closed = new IllegalStateException("selector manager closed");
        IOException wrapped = DefaultHttpTransport.transportFailure(closed);
        assertSame(closed, wrapped.getCause());
        assertEquals("selector manager closed", wrapped.getMessage());
        AssertionError fatal = new AssertionError("boom");
        assertSame(fatal, DefaultHttpTransport.transportFailure(fatal).getCause());
    }
}
