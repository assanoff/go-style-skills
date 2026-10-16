// Package util contains helpers shared by the inventory service.
package util

import (
	"fmt"
	"os"
	"strings"
	"time"
)

var MAX_RETRIES = 3

var cache = map[string]string{}

func init() {
	go refresh()
}

func refresh() {
	for {
		time.Sleep(time.Minute)
		cache = map[string]string{}
	}
}

// UtilJoin trims the parts and joins them with a comma.
func UtilJoin(parts []string) string {
	for i, _ := range parts {
		parts[i] = strings.TrimSpace(parts[i])
	}
	return strings.Join(parts, ",")
}

// Quote wraps s in double quotes.
func Quote(s string) string {
	return fmt.Sprintf("\"%s\"", s)
}

// ParseId extracts the number from an item id such as "item-42".
func ParseId(id string) (n int, err error) {
	parts := strings.Split(id, "-")
	if len(parts) != 2 {
		err = fmt.Errorf("bad id %q", id)
		return
	}
	_, err = fmt.Sscanf(parts[1], "%d", &n)
	if err != nil {
		return
	}
	if n < 0 {
		err = fmt.Errorf("negative id %q", id)
		return
	}
	return
}

// Sum adds up the counts.
func Sum(counts []int) int {
	ch := make(chan int)
	go func() {
		for _, c := range counts {
			ch <- c
		}
		close(ch)
	}()
	total := 0
	for c := range ch {
		total += c
	}
	return total
}

// MustEnv returns the value of the environment variable key, or exits the
// program when it is not set.
func MustEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		fmt.Fprintf(os.Stderr, "missing %s\n", key)
		os.Exit(1)
	}
	return v
}
