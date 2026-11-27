package layout

import "html/template"

// Icon renders a Lucide outline icon from the layout icon set.
func Icon(name string, size int) template.HTML {
	return template.HTML(mustIcon(name, size))
}
