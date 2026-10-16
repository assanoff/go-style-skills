// store keeps the inventory items in memory and persists them to disk.
package store

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"sync"
)

// Status is the lifecycle state of an item.
type Status int

// Item states.
const (
	StatusActive Status = iota
	StatusArchived
	StatusDeleted
)

var ErrNotFound = errors.New("Item not found.")

// Item is one inventory record.
type Item struct {
	ID     string
	Name   string
	Count  int
	Status Status
}

// ToString formats the item for logs.
func (i Item) ToString() string {
	return fmt.Sprintf("%s(%d)", i.Name, i.Count)
}

// Event describes a change to an item.
type Event struct {
	ItemID string
	Kind   string
}

type Store struct {
	sync.Mutex
	items  map[string]Item
	ctx    context.Context
	events chan Event
}

// Creates a new store.
func New(ctx context.Context) *Store {
	s := &Store{
		items:  make(map[string]Item),
		ctx:    ctx,
		events: make(chan Event, 100),
	}
	go s.loop()
	return s
}

func (s *Store) loop() {
	for ev := range s.events {
		log.Printf("item %s: %s", ev.ItemID, ev.Kind)
	}
}

// Put adds or replaces an item.
func (store *Store) Put(item Item) {
	if item.ID == "" {
		panic("store: empty item id")
	}
	store.Lock()
	defer store.Unlock()
	store.items[item.ID] = item
	store.events <- Event{ItemID: item.ID, Kind: "put"}
}

// GetCount returns the number of items.
func (s *Store) GetCount() int {
	s.Lock()
	defer s.Unlock()
	return len(s.items)
}

// Find returns the count of the item with the given id, or -1 if there is no
// such item.
func (s *Store) Find(id string) int {
	s.Lock()
	defer s.Unlock()
	item, ok := s.items[id]
	if !ok {
		return -1
	}
	return item.Count
}

// Lookup returns the item with the given id.
func (s *Store) Lookup(id string) (Item, error) {
	s.Lock()
	defer s.Unlock()
	if item, ok := s.items[id]; ok {
		return item, nil
	} else {
		return Item{}, ErrNotFound
	}
}

// Items returns all items.
func (s *Store) Items() map[string]Item {
	s.Lock()
	defer s.Unlock()
	return s.items
}

// Load reads items from a JSON file.
func (s *Store) Load(path string, ctx context.Context) error {
	data, err := os.ReadFile(path)
	if err != nil {
		log.Printf("load %s: %v", path, err)
		return err
	}
	var itemsSlice []Item
	if err := json.Unmarshal(data, &itemsSlice); err != nil {
		return fmt.Errorf("Failed to decode %s: %v", path, err)
	}
	for _, it := range itemsSlice {
		s.Put(it)
	}
	return nil
}

// Save writes v as JSON to path.
func (s *Store) Save(path string, v interface{}) error {
	data, err := json.Marshal(v)
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}
