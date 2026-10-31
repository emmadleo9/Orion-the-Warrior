package com.rmyndharis.openwa.model;

import com.google.gson.annotations.SerializedName;

/**
 * The kind of call a link opens. The wire values are lowercase, so each constant carries a
 * {@link SerializedName} mapping.
 */
public enum CallLinkType {
    @SerializedName("audio")
    AUDIO,
    @SerializedName("video")
    VIDEO
}
