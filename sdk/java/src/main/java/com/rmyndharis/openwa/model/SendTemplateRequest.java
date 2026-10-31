package com.rmyndharis.openwa.model;

import java.util.List;
import java.util.Map;

/** Request body for rendering and sending a stored message template. */
public record SendTemplateRequest(
    String chatId, String templateId, String templateName, Map<String, String> vars, List<String> mentions,
    Boolean linkPreview) {
    /** Back-compatible constructor without the send-text passthrough options. */
    public SendTemplateRequest(String chatId, String templateId, String templateName, Map<String, String> vars) {
        this(chatId, templateId, templateName, vars, null, null);
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String chatId;
        private String templateId;
        private String templateName;
        private Map<String, String> vars;
        private List<String> mentions;
        private Boolean linkPreview;

        public Builder chatId(String v) {
            this.chatId = v;
            return this;
        }

        /** Provide exactly one of {@code templateId} or {@code templateName}. */
        public Builder templateId(String v) {
            this.templateId = v;
            return this;
        }

        /** Provide exactly one of {@code templateId} or {@code templateName}. */
        public Builder templateName(String v) {
            this.templateName = v;
            return this;
        }

        /** Template variables (server DTO field is {@code vars}). */
        public Builder vars(Map<String, String> v) {
            this.vars = v;
            return this;
        }

        /** WIDs to @mention in the rendered body, which must carry the matching @&lt;number&gt; token. */
        public Builder mentions(List<String> v) {
            this.mentions = v;
            return this;
        }

        /** Controls the URL preview on the rendered body, with the same engine split as send-text. */
        public Builder linkPreview(Boolean v) {
            this.linkPreview = v;
            return this;
        }

        public SendTemplateRequest build() {
            return new SendTemplateRequest(chatId, templateId, templateName, vars, mentions, linkPreview);
        }
    }
}
