// Package notify sends notifications about inventory changes.
package notify

import (
	"fmt"
	"net/http"
	"strings"
	"time"
)

// Notifier posts messages to a webhook.
type Notifier struct {
	URL     string
	Timeout int
	Verbose bool
	tags    []string
	client  *http.Client
}

// NewNotifier creates a Notifier.
func NewNotifier(url string, timeout int, verbose bool) *Notifier {
	n := new(Notifier)
	n.URL = url
	n.Timeout = timeout
	n.Verbose = verbose
	n.client = &http.Client{Timeout: time.Duration(timeout) * time.Second}
	return n
}

// Default is the notifier used by Send.
var Default = NewNotifier("http://localhost:8080/hook", 5, false)

// Send posts msg with the default notifier.
func Send(msg string) error {
	return Default.Post(msg, true, false)
}

// SetTags sets the tags added to every message.
func (n *Notifier) SetTags(tags []string) {
	n.tags = tags
}

// Post sends msg. If urgent is set the message is prefixed; if dryRun is set
// the payload is printed instead of sent.
func (n *Notifier) Post(msg string, urgent bool, dryRun bool) error {
	var body string
	if urgent {
		body = "URGENT: " + msg
	} else {
		body = msg
	}
	if len(n.tags) > 0 {
		body += " [" + strings.Join(n.tags, ",") + "]"
	}
	payload := "{\"text\": \"" + body + "\"}"
	if dryRun {
		fmt.Println(payload)
		return nil
	}
	resp, err := n.client.Post(n.URL, "application/json", strings.NewReader(payload))
	if err != nil {
		return fmt.Errorf("failed to post notification: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("notify: unexpected status %d", resp.StatusCode)
	}
	return nil
}

// Format renders an item line.
func Format(name string, count int) string {
	return fmt.Sprintf("%s: %s", name, fmt.Sprint(count))
}

// Level classifies a stock count.
func Level(count int) string {
	switch true {
	case count == 0:
		return "empty"
	case count < 10:
		return "low"
	}
	return "ok"
}

// Settings configures a batch of notifications.
type Settings struct {
	Name    string
	Retries int
	Verbose bool
}

// Settings for the default batch.
func DefaultSettings() Settings {
	return Settings{Name: "default", Retries: 0, Verbose: false}
}
