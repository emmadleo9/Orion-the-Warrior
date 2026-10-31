package com.rmyndharis.openwa.model;

import com.google.gson.annotations.SerializedName;

/**
 * The scheme of a session proxy. The wire values are lowercase, so each constant carries a
 * {@link SerializedName} mapping.
 */
public enum ProxyType {
    @SerializedName("http")
    HTTP,
    @SerializedName("https")
    HTTPS,
    @SerializedName("socks4")
    SOCKS4,
    @SerializedName("socks5")
    SOCKS5
}
