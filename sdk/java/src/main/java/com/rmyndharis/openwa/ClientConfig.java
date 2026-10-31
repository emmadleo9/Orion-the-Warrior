package com.rmyndharis.openwa;

import com.rmyndharis.openwa.http.HttpTransport;
import java.net.URI;
import java.net.URISyntaxException;
import java.time.Duration;
import java.util.Map;

/** Immutable client configuration. Build via {@link #builder()}. */
public final class ClientConfig {
    final String baseUrl;
    final String apiKey;
    final Duration timeout;
    final Map<String, String> defaultHeaders;
    final HttpTransport transport; // nullable → OpenWAClient supplies DefaultHttpTransport

    private ClientConfig(Builder b) {
        String url = b.baseUrl == null ? null : b.baseUrl.strip();
        if (url == null || url.isEmpty()) {
            throw new IllegalArgumentException("OpenWAClient: baseUrl is required");
        }
        try {
            new URI(url);
        } catch (URISyntaxException e) {
            throw new IllegalArgumentException("OpenWAClient: baseUrl is not a valid URL: " + url);
        }
        String key = b.apiKey == null ? null : b.apiKey.strip();
        if (key == null || key.isEmpty()) {
            throw new IllegalArgumentException("OpenWAClient: apiKey is required");
        }
        if (hasIllegalChar(key)) {
            throw new IllegalArgumentException(
                "OpenWAClient: apiKey contains illegal characters (control or non-ASCII) — check for a stray newline");
        }
        if (b.timeout != null && (b.timeout.isZero() || b.timeout.isNegative())) {
            throw new IllegalArgumentException("OpenWAClient: timeout must be positive");
        }
        warnIfInsecureHttp(url);
        // baseUrl/apiKey are stripped so a trailing newline from a file/env var can't break the request.
        this.baseUrl = url;
        this.apiKey = key;
        this.timeout = b.timeout != null ? b.timeout : Duration.ofSeconds(30);
        // Copied so a later change to the caller's map cannot alter the headers of this client, and so
        // a null key or value fails here instead of as a raw NullPointerException on the first request.
        try {
            this.defaultHeaders = b.defaultHeaders != null ? Map.copyOf(b.defaultHeaders) : Map.of();
        } catch (NullPointerException e) {
            throw new IllegalArgumentException("OpenWAClient: defaultHeaders must not contain null keys or values");
        }
        // A value the HTTP stack refuses (a trailing newline from a token file) is named here, without the
        // value: the stack's own message would quote it, and a proxy credential carried in a header would
        // reach the application's logs.
        for (Map.Entry<String, String> header : this.defaultHeaders.entrySet()) {
            if (!isToken(header.getKey())) {
                throw new IllegalArgumentException(
                    "OpenWAClient: defaultHeaders has a header name that is not a valid HTTP token");
            }
            if (hasIllegalHeaderValueChar(header.getValue())) {
                throw new IllegalArgumentException(
                    "OpenWAClient: defaultHeaders value for '" + header.getKey()
                        + "' contains illegal characters (control or non-ASCII) - check for a stray newline");
            }
        }
        this.transport = b.transport;
    }

    private static boolean isToken(String name) {
        if (name.isEmpty()) {
            return false;
        }
        for (int i = 0; i < name.length(); i++) {
            char c = name.charAt(i);
            boolean alnum = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
            if (!alnum && "!#$%&'*+-.^_`|~".indexOf(c) < 0) {
                return false;
            }
        }
        return true;
    }

    private static boolean hasIllegalHeaderValueChar(String value) {
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c != '\t' && (c < 0x20 || c > 0x7e)) {
                return true;
            }
        }
        return false;
    }

    private static boolean hasIllegalChar(String s) {
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < 0x20 || c > 0x7e) {
                return true;
            }
        }
        return false;
    }

    /**
     * Warn (not throw) when baseUrl is {@code http://} and the host is not localhost. The API key
     * is sent as an {@code X-API-Key} header on every request — over plaintext http to a non-local
     * host that's cleartext on the wire. Warning (not refusing) keeps local dev and
     * TLS-terminating-proxy topologies working.
     */
    private static void warnIfInsecureHttp(String url) {
        try {
            URI uri = new URI(url);
            String scheme = uri.getScheme();
            String host = uri.getHost();
            if ("http".equalsIgnoreCase(scheme) && host != null) {
                String h = host.replaceAll("^\\[|\\]$", "").toLowerCase();
                if (!h.equals("localhost") && !h.equals("127.0.0.1") && !h.equals("::1")) {
                    System.err.println(
                        "[OpenWA SDK] WARNING: baseUrl uses an insecure http:// URL (host: " + host + "). "
                            + "The API key will be sent in cleartext. Use https:// in production.");
                }
            }
        } catch (URISyntaxException e) {
            // Already validated above — a repeat failure here is a no-op.
        }
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String baseUrl;
        private String apiKey;
        private Duration timeout;
        private Map<String, String> defaultHeaders;
        private HttpTransport transport;

        /** Base URL of the OpenWA API, e.g. {@code http://localhost:2785}. */
        public Builder baseUrl(String v) {
            this.baseUrl = v;
            return this;
        }

        /** API key sent as {@code X-API-Key}. */
        public Builder apiKey(String v) {
            this.apiKey = v;
            return this;
        }

        /** Per-request timeout (default 30s), covering the whole exchange, response body included, with the default transport. */
        public Builder timeout(Duration v) {
            this.timeout = v;
            return this;
        }

        /** Default headers applied to every request (auth + JSON content-type always win). */
        public Builder defaultHeaders(Map<String, String> v) {
            this.defaultHeaders = v;
            return this;
        }

        /** Injectable transport; defaults to {@link com.rmyndharis.openwa.http.DefaultHttpTransport}. */
        public Builder transport(HttpTransport v) {
            this.transport = v;
            return this;
        }

        public ClientConfig build() {
            return new ClientConfig(this);
        }
    }
}
