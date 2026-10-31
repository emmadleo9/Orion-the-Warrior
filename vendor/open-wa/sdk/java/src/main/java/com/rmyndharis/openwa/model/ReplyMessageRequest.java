package com.rmyndharis.openwa.model;

import java.util.List;

/** Request body for replying to a specific message. */
public record ReplyMessageRequest(String chatId, String quotedMessageId, String text, List<String> mentions) {
    /** Back-compatible constructor without mentions. */
    public ReplyMessageRequest(String chatId, String quotedMessageId, String text) {
        this(chatId, quotedMessageId, text, null);
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String chatId;
        private String quotedMessageId;
        private String text;
        private List<String> mentions;

        public Builder chatId(String v) {
            this.chatId = v;
            return this;
        }

        public Builder quotedMessageId(String v) {
            this.quotedMessageId = v;
            return this;
        }

        public Builder text(String v) {
            this.text = v;
            return this;
        }

        /** WIDs to @mention; the text must also contain the matching @&lt;number&gt; token. */
        public Builder mentions(List<String> v) {
            this.mentions = v;
            return this;
        }

        public ReplyMessageRequest build() {
            return new ReplyMessageRequest(chatId, quotedMessageId, text, mentions);
        }
    }
}
