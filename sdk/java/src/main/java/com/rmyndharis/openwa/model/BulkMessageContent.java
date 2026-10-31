package com.rmyndharis.openwa.model;

import java.util.List;

/** Content payload for one bulk-send item. Populate the field matching the item's {@link BulkMessageType}. */
public record BulkMessageContent(
    String text,
    BulkMediaRequest image,
    BulkMediaRequest video,
    BulkMediaRequest audio,
    BulkMediaRequest document,
    String caption,
    List<String> mentions) {
    /** Back-compatible constructor without mentions. */
    public BulkMessageContent(
        String text, BulkMediaRequest image, BulkMediaRequest video, BulkMediaRequest audio,
        BulkMediaRequest document, String caption) {
        this(text, image, video, audio, document, caption, null);
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String text;
        private BulkMediaRequest image;
        private BulkMediaRequest video;
        private BulkMediaRequest audio;
        private BulkMediaRequest document;
        private String caption;
        private List<String> mentions;

        public Builder text(String v) {
            this.text = v;
            return this;
        }

        public Builder image(BulkMediaRequest v) {
            this.image = v;
            return this;
        }

        public Builder video(BulkMediaRequest v) {
            this.video = v;
            return this;
        }

        public Builder audio(BulkMediaRequest v) {
            this.audio = v;
            return this;
        }

        public Builder document(BulkMediaRequest v) {
            this.document = v;
            return this;
        }

        public Builder caption(String v) {
            this.caption = v;
            return this;
        }

        /** Per item: a batch fans out to many chats, and a WID is only taggable in a chat it is in. */
        public Builder mentions(List<String> v) {
            this.mentions = v;
            return this;
        }

        public BulkMessageContent build() {
            return new BulkMessageContent(text, image, video, audio, document, caption, mentions);
        }
    }
}
