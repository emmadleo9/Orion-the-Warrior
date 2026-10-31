/**
 * Decoded-byte cap for inline base64 media in outbound event payloads. Shared by the webhook
 * delivery path and the WebSocket gateway so both sinks emit the SAME contract for an over-cap
 * blob. 1 MiB; override with WEBHOOK_MEDIA_INLINE_MAX_BYTES (0 = never inline media).
 */
export const DEFAULT_WEBHOOK_MEDIA_INLINE_MAX_BYTES = 1024 * 1024;

/**
 * Replace an over-cap inline base64 `media.data` blob with the declared-only omitted marker
 * ({ mimetype, filename?, omitted: true, sizeBytes }), the same contract the inbound media cap
 * and the status store already emit, so the multi-MB blob is never cloned per webhook, queued
 * into Redis, or POSTed. Returns the ORIGINAL object when nothing was shed (zero-copy fast path);
 * otherwise a shallow copy with only `media` replaced, so the caller's event data is never
 * mutated. `maxBytes` compares against the DECODED size; 0 sheds any inline blob.
 */
export function shedInlineMedia(data: Record<string, unknown>, maxBytes: number): Record<string, unknown> {
  if (!data || typeof data !== 'object') return data;
  const media = data.media as { mimetype?: unknown; filename?: unknown; data?: unknown; omitted?: unknown } | undefined;
  if (!media || typeof media !== 'object' || typeof media.data !== 'string' || media.data.length === 0) {
    return data;
  }
  const sizeBytes = Buffer.byteLength(media.data, 'base64');
  if (sizeBytes <= maxBytes) return data;
  return {
    ...data,
    media: {
      mimetype: media.mimetype,
      ...(typeof media.filename === 'string' ? { filename: media.filename } : {}),
      omitted: true,
      sizeBytes,
    },
  };
}
