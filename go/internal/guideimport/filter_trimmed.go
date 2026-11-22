package guideimport

import "strings"

// FilterTrimmed runs FilterCodes on every string value in trimmed import data.
func FilterTrimmed(data Trimmed) (Trimmed, int) {
	total := 0
	out := make(Trimmed, len(data))
	for i, e := range data {
		out[i] = e
		if s, ok := e.Value.(string); ok {
			clean, n := FilterCodes(s)
			out[i].Value = clean
			total += n
		}
	}
	return out, total
}

func nullIfZero(n int) any {
	if n == 0 {
		return nil
	}
	return n
}

func trimmedHasText(data Trimmed) bool {
	for _, e := range data {
		if e.Key == "source" {
			continue
		}
		switch v := e.Value.(type) {
		case string:
			if strings.TrimSpace(v) != "" {
				return true
			}
		case []string:
			for _, s := range v {
				if strings.TrimSpace(s) != "" {
					return true
				}
			}
		}
	}
	return false
}