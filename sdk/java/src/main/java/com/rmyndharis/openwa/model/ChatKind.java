package com.rmyndharis.openwa.model;

import com.google.gson.annotations.SerializedName;

/** The conversation kind a chat or message belongs to. */
public enum ChatKind {
    @SerializedName("individual") INDIVIDUAL,
    @SerializedName("group") GROUP,
    @SerializedName("channel") CHANNEL,
    @SerializedName("status") STATUS,
    @SerializedName("broadcast") BROADCAST,
    @SerializedName("unknown") UNKNOWN
}
