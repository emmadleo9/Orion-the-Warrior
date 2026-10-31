package com.rmyndharis.openwa.http;

import java.time.Duration;
import java.util.Map;
import java.util.Set;

/** A fully-resolved outbound request (absolute URL, final headers, serialized body). */
public record HttpRequestData(HttpMethod method, String url, Map<String, String> headers, String body, Duration timeout) {
    /** Header values and the body are left out: a logging transport prints the request it is handed. */
    @Override
    public String toString() {
        return "HttpRequestData[method=" + method + ", url=" + url
            + ", headers=" + (headers == null ? Set.of() : headers.keySet())
            + ", bodyLength=" + (body == null ? 0 : body.length()) + ", timeout=" + timeout + "]";
    }
}
