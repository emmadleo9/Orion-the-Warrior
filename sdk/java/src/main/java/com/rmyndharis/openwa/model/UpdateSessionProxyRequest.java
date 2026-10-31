package com.rmyndharis.openwa.model;

/**
 * Update per-session proxy settings. Send {@code proxyUrl: null} to clear.
 * Changes apply on the next start, not to a running engine.
 */
public record UpdateSessionProxyRequest(String proxyUrl) {}
