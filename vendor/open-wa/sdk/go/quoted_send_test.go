package openwa

import (
	"context"
	"encoding/json"
	"testing"
)

// The body is what matters here, not the path. A dropped key is the failure mode this guards: Go's
// `omitempty` and Java's Gson both omit an unset value, so a request type that forgot the field
// still compiles, still routes correctly, and simply sends nothing — a 400 on one client while the
// others work.
func TestQuotedMessageIDReachesTheBody(t *testing.T) {
	ctx := context.Background()
	cases := []struct {
		name string
		call func(*Client)
	}{
		{"send-text", func(c *Client) {
			c.Messages.SendText(ctx, "s1", SendTextRequest{ChatID: "a@c.us", Text: "hi", QuotedMessageID: "q1"})
		}},
		{"send-image", func(c *Client) {
			c.Messages.SendImage(ctx, "s1", SendMediaRequest{ChatID: "a@c.us", URL: "http://u", QuotedMessageID: "q1"})
		}},
		{"send-audio", func(c *Client) {
			c.Messages.SendAudio(ctx, "s1", SendAudioRequest{ChatID: "a@c.us", URL: "http://u", QuotedMessageID: "q1"})
		}},
		{"send-location", func(c *Client) {
			c.Messages.SendLocation(ctx, "s1", SendLocationRequest{ChatID: "a@c.us", Latitude: 1, Longitude: 2, QuotedMessageID: "q1"})
		}},
		{"send-contact", func(c *Client) {
			c.Messages.SendContact(ctx, "s1", SendContactRequest{ChatID: "a@c.us", ContactName: "A", ContactNumber: "628", QuotedMessageID: "q1"})
		}},
		{"send-poll", func(c *Client) {
			c.Messages.SendPoll(ctx, "s1", SendPollRequest{ChatID: "a@c.us", Name: "Q", Options: []string{"a", "b"}, QuotedMessageID: "q1"})
		}},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			rt := &recordTransport{status: 200, body: `{}`}
			tc.call(newTestClient(t, rt))

			var body map[string]any
			if err := json.Unmarshal(rt.lastRaw, &body); err != nil {
				t.Fatalf("request body was not JSON: %v (%s)", err, rt.lastRaw)
			}
			if body["quotedMessageId"] != "q1" {
				t.Fatalf("quotedMessageId missing from body: %s", rt.lastRaw)
			}
		})
	}
}

// Known-negative control. `omitempty` is the whole reason the field is a plain string rather than a
// pointer, and without this an implementation that emitted `"quotedMessageId": ""` on every send
// would satisfy nothing above yet ship a wrong body on the ordinary path.
func TestOrdinarySendOmitsTheQuoteKey(t *testing.T) {
	rt := &recordTransport{status: 200, body: `{}`}
	c := newTestClient(t, rt)
	c.Messages.SendImage(context.Background(), "s1", SendMediaRequest{ChatID: "a@c.us", URL: "http://u"})

	var body map[string]any
	if err := json.Unmarshal(rt.lastRaw, &body); err != nil {
		t.Fatalf("request body was not JSON: %v", err)
	}
	if _, present := body["quotedMessageId"]; present {
		t.Fatalf("ordinary send carried a quote key: %s", rt.lastRaw)
	}
}
