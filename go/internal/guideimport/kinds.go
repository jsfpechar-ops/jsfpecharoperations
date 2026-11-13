package guideimport

// The guide card vocabulary of App/app/guest_guide.py. Order matters: the
// position of a kind is its sort_order, and the JSON schema lists them in this
// order. testdata/golden.json (written by guide_import_golden.py) pins all of it.

// Topics is guest_guide.TOPICS.
var Topics = []string{
	"arrival", "wifi", "heating", "kitchen", "rooms", "bathroom", "rules", "trash", "checkout", "area", "emergency",
}

// KindTopic is one built-in card kind and its topic.
type KindTopic struct{ Kind, Topic string }

// Kinds is guest_guide.KINDS in guest order.
var Kinds = []KindTopic{
	{"checkin", "arrival"}, {"keys", "arrival"}, {"getting_here", "arrival"}, {"parking", "arrival"},
	{"garage", "arrival"}, {"wifi", "wifi"}, {"tv", "wifi"}, {"heating", "heating"},
	{"hot_water", "heating"}, {"air_conditioning", "heating"}, {"kitchen_appliances", "kitchen"},
	{"dishwasher", "kitchen"}, {"coffee_machine", "kitchen"}, {"bedrooms", "rooms"},
	{"sofa_bed", "rooms"}, {"balcony", "rooms"}, {"bathroom", "bathroom"},
	{"washing_machine", "bathroom"}, {"house_rules", "rules"}, {"trash", "trash"},
	{"checkout", "checkout"}, {"area_tips", "area"}, {"emergency", "emergency"},
	{"something_wrong", "emergency"},
}

// Limits is guest_guide.LIMITS for the four card text fields.
var Limits = map[string]int{"title": 120, "location": 500, "steps": 4000, "watch_out": 1000}

func kindOrder(kind string) (int, bool) {
	for i, k := range Kinds {
		if k.Kind == kind {
			return i, true
		}
	}
	return len(Kinds), false
}

func topicOK(topic string) bool {
	for _, t := range Topics {
		if t == topic {
			return true
		}
	}
	return false
}
