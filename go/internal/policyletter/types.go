package policyletter

// MaxLetterChars is the longest pasted police letter the parser accepts.
const MaxLetterChars = 20000

// Fields are the apartment columns the letter can pre-fill (not password).
var Fields = []string{"uby_idub", "uby_ws_user", "uby_mark"}

// FilledStates are field states that carry a value from the letter.
var FilledStates = map[string]bool{
	"found":   true,
	"derived": true,
}

// FieldResult is one parsed value or a refusal reason.
type FieldResult struct {
	State string
	Value string
	Line  int // 1-based, 0 when unset
	Label string
	Lines []int
	// Source slices: label through value, never a whole line; only when filled.
	Source []string
}

// LetterResult is the full parse outcome.
type LetterResult struct {
	Status   string
	Fields   map[string]FieldResult
	Password FieldResult // not included in String()
	Facility FieldResult
}

// String omits the password so a logged result never shows it (1100).
func (r LetterResult) String() string {
	return formatLetterResult(r, false)
}
