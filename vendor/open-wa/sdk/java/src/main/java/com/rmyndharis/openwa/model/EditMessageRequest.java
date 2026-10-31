package com.rmyndharis.openwa.model;

import java.util.List;

/** Request body for editing the text of a message sent by this account. */
public record EditMessageRequest(String chatId, String messageId, String body, List<String> mentions) {
    /** Back-compatible constructor without mentions. */
    public EditMessageRequest(String chatId, String messageId, String body) {
        this(chatId, messageId, body, null);
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String chatId;
        private String messageId;
        private String body;
        private List<String> mentions;

        public Builder chatId(String v) {
            this.chatId = v;
            return this;
        }

        public Builder messageId(String v) {
            this.messageId = v;
            return this;
        }

        /** The replacement message text. */
        public Builder body(String v) {
            this.body = v;
            return this;
        }

        /** An edit REPLACES the body, so tags are re-applied rather than preserved. */
        public Builder mentions(List<String> v) {
            this.mentions = v;
            return this;
        }

        public EditMessageRequest build() {
            return new EditMessageRequest(chatId, messageId, body, mentions);
        }
    }
}
