package com.rmyndharis.openwa.model;

/**
 * Masked per-session proxy configuration returned by GET/PATCH /api/sessions/{id}/proxy.
 * Credentials are never included.
 */
public record SessionProxy(
    boolean enabled,
    ProxyType proxyType,
    String proxyHost,
    boolean hasCredentials
) {}
