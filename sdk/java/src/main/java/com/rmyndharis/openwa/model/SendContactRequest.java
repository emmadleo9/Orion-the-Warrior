package com.rmyndharis.openwa.model;

/** Request body for sending a contact card. */
public record SendContactRequest(String chatId, String contactName, String contactNumber,
    String quotedMessageId) {
    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String chatId;
        private String contactName;
        private String contactNumber;
        private String quotedMessageId;

        public Builder chatId(String v) {
            this.chatId = v;
            return this;
        }

        public Builder contactName(String v) {
            this.contactName = v;
            return this;
        }

        public Builder contactNumber(String v) {
            this.contactNumber = v;
            return this;
        }

        /**
         * Quote an earlier message, turning this send into a reply. Engine-specific:
         * whatsapp-web.js matches the serialized message id, Baileys the raw key id of a message
         * it has already stored.
         */
        public Builder quotedMessageId(String v) {
            this.quotedMessageId = v;
            return this;
        }

        public SendContactRequest build() {
            return new SendContactRequest(chatId, contactName, contactNumber, quotedMessageId);
        }
    }
}
