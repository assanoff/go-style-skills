// Command inventory loads the item file and reports the stock.
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"

	. "example.com/inventory/internal/notify"
	_ "net/http/pprof"
	store "example.com/inventory/internal/store"
	"example.com/inventory/pkg/util"
)

func main() {
	path := flag.String("data", "items.json", "path to the items file")
	flag.Parse()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	s := store.New(ctx)
	if err := s.Load(*path, ctx); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := Send(fmt.Sprintf("loaded %d items", s.GetCount())); err != nil {
		log.Fatal(err)
	}
	if util.MustEnv("INVENTORY_MODE") == "check" {
		os.Exit(2)
	}
}
