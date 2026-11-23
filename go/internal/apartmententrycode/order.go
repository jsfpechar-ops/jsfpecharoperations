// Package apartmententrycode orders an apartment's extra entry codes for guests:
// gate, building entrance, the TTLock apartment door, then garage, bike room, other
// (owner 2026-11-22, D5). Same type keeps the host's position order.
package apartmententrycode

import "sort"

type Row struct {
	Position int
	CodeType string
}

type Slot struct {
	Door bool
	Row  Row
}

var emitOrder = []string{"gate", "building_entrance", "garage", "bike_room", "other"}

func EntryCodeGuestOrder(rows []Row, hasLock bool) []Slot {
	byType := make(map[string][]Row)
	for _, row := range rows {
		byType[row.CodeType] = append(byType[row.CodeType], row)
	}
	for typ := range byType {
		sort.SliceStable(byType[typ], func(i, j int) bool {
			return byType[typ][i].Position < byType[typ][j].Position
		})
	}
	out := make([]Slot, 0, len(rows)+1)
	for _, typ := range emitOrder {
		for _, row := range byType[typ] {
			out = append(out, Slot{Row: row})
		}
		if hasLock && typ == "building_entrance" {
			out = append(out, Slot{Door: true})
			hasLock = false
		}
	}
	if hasLock {
		out = append(out, Slot{Door: true})
	}
	return out
}
