package com.rmyndharis.openwa.model;

/** Request body for subscribing to a chat's presence. */
public record SubscribePresenceRequest(String chatId) {
    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String chatId;

        /** WhatsApp chat id (JID), e.g. {@code 628123456789@c.us}. */
        public Builder chatId(String v) {
            this.chatId = v;
            return this;
        }

        public SubscribePresenceRequest build() {
            return new SubscribePresenceRequest(chatId);
        }
    }
}
