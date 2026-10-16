package store

import (
	"context"
	"reflect"
	"testing"

	"github.com/stretchr/testify/assert"
)

func newTestStore(t *testing.T) *Store {
	s := New(context.Background())
	s.Put(Item{ID: "a", Name: "apple", Count: 3})
	return s
}

func TestFind(t *testing.T) {
	s := newTestStore(t)
	tests := []struct {
		id   string
		want int
	}{
		{"a", 3},
		{"missing", -1},
	}
	for _, tt := range tests {
		got := s.Find(tt.id)
		if got != tt.want {
			t.Errorf("expected %d, got %d", tt.want, got)
		}
	}
}

func TestItems(t *testing.T) {
	s := newTestStore(t)
	want := map[string]Item{"a": {ID: "a", Name: "apple", Count: 3}}
	if !reflect.DeepEqual(s.Items(), want) {
		t.Error("wrong items")
	}
}

func TestPutConcurrent(t *testing.T) {
	s := newTestStore(t)
	done := make(chan struct{})
	go func() {
		defer close(done)
		if s.GetCount() == 0 {
			t.Fatal("store is empty")
		}
	}()
	<-done
}

func TestLookup(t *testing.T) {
	s := newTestStore(t)
	item, err := s.Lookup("a")
	assert.NoError(t, err)
	assert.Equal(t, "apple", item.Name)
}
