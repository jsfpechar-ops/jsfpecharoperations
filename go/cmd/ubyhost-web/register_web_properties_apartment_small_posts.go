package main

// Brief 1703: the five property POSTs not yet on UBYHOST_GO_PATHS (dormant until 1705).

import (
	"net"
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/web/properties"
)

func init() {
	registerRoutes(registerWebPropertiesApartmentSmallPosts)
}

func registerWebPropertiesApartmentSmallPosts(mux *http.ServeMux, m *metrics, pool *pgxpool.Pool) {
	fetch := &ical.FetchOptions{Resolver: net.DefaultResolver, AllowPrivate: ical.AllowPrivate(os.Getenv)}
	properties.RegisterApartmentSmallPosts(mux, m.wrap, pool, os.Getenv, time.Now, fetch)
}
