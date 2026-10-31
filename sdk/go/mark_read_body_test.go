package openwa

import (
	"context"
	"strings"
	"testing"
)

// The three states of messageIds differ on the wire, and a plain []string with omitempty could not
// tell two of them apart: an empty slice was dropped, so a caller asking for nothing to be
// acknowledged silently acknowledged the newest message instead. The pointer makes "absent" and
// "empty" distinct, and this pins all three so the tag cannot quietly go back.
func TestMarkReadBodyDistinguishesAbsentFromEmpty(t *testing.T) {
	empty := []string{}
	named := []string{"3EB0C767D26B8A3F1A2B"}

	cases := []struct {
		name string
		body MarkChatReadRequest
		want string
	}{
		{"absent omits the key", MarkChatReadRequest{ChatID: "628123@c.us"}, `{"chatId":"628123@c.us"}`},
		{"empty sends []", MarkChatReadRequest{ChatID: "628123@c.us", MessageIDs: &empty}, `"messageIds":[]`},
		{"named sends the ids", MarkChatReadRequest{ChatID: "628123@c.us", MessageIDs: &named}, `"messageIds":["3EB0C767D26B8A3F1A2B"]`},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			rt := &recordTransport{status: 200, body: `{"success":true}`}
			c := newTestClient(t, rt)

			if _, err := c.Chats.MarkRead(context.Background(), "s1", tc.body); err != nil {
				t.Fatalf("MarkRead: %v", err)
			}
			if got := string(rt.lastRaw); !strings.Contains(got, tc.want) {
				t.Fatalf("body = %s, want it to contain %s", got, tc.want)
			}
		})
	}

	// The absent case must ALSO not carry the key at all, which "contains" cannot express.
	rt := &recordTransport{status: 200, body: `{"success":true}`}
	c := newTestClient(t, rt)
	if _, err := c.Chats.MarkRead(context.Background(), "s1", MarkChatReadRequest{ChatID: "628123@c.us"}); err != nil {
		t.Fatalf("MarkRead: %v", err)
	}
	if strings.Contains(string(rt.lastRaw), "messageIds") {
		t.Fatalf("absent body must omit messageIds entirely, got %s", rt.lastRaw)
	}
}
