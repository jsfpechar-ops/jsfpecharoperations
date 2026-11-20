package doorcodes

import "github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ttlock"

// Door code states (door_code.state). Ports the constants at the top of App/app/door_codes.py.
const (
	StatePending       = "pending"
	StateIssuing       = "issuing"
	StateRetrying      = "retrying"
	StateIssued        = "issued"
	StateFailed        = "failed"
	StateExpired       = "expired"
	StateRevokePending = "revoke_pending"
	StateRevoked       = "revoked"
	StateRevokeFailed  = "revoke_failed"
)

// transitions is Python TRANSITIONS. Python declares it and does not enforce it; the Go
// port checks every move issue makes against it in tests (allowedMove).
var transitions = map[string]map[string]bool{
	StatePending:       {StateIssuing: true, StateRevoked: true, StateExpired: true},
	StateRetrying:      {StateIssuing: true, StateRevoked: true, StateExpired: true},
	StateIssuing:       {StatePending: true, StateExpired: true, StateRetrying: true, StateIssued: true, StateFailed: true},
	StateIssued:        {StateRevokePending: true, StateExpired: true, StatePending: true},
	StateRevokePending: {StateIssued: true, StateRevoked: true, StateRevokeFailed: true},
	StateRevokeFailed:  {StateIssued: true},
	StateFailed:        {},
	StateExpired:       {},
	StateRevoked:       {},
}

// allowedMove reports whether the TRANSITIONS table has the move from -> to.
func allowedMove(from, to string) bool {
	return transitions[from][to]
}

// Python BACKOFF_MINUTES: retry delay after the n-th failed try is BackoffMinutes[n-1].
var backoffMinutes = []int{1, 5, 15, 60, 240}

const (
	// IssueMaxAttempts: a failed code is handed to the host after this many tries.
	IssueMaxAttempts = 2
	// PeriodTaken and PeriodShared are the error kinds for a period that already holds a code.
	PeriodTaken  = ttlock.KindPeriodTaken
	PeriodShared = "period_shared"
	// PeriodTakenMaxAttempts: a period-taken row is handed over after this many tries.
	PeriodTakenMaxAttempts = 4
	// LeaseMinutes: a claim older than this may be taken again (reconcile lease).
	LeaseMinutes = 2
	// DelayMinutes: a guest who has finished registering must not wait longer than this.
	DelayMinutes = 5
	// Batch is the row limit for the batch queries in this package.
	Batch = 20
	// HoldConfirmationMinutes: no held registration confirmation waits longer than this.
	HoldConfirmationMinutes = 5
	// KeypadConfirmSuffix is the # the guest presses to confirm the PIN.
	KeypadConfirmSuffix = "#"
)

// periodTakenRetryMinutes: delays for a period-taken row, indexed by attempts-2 (clamped to 0..1).
var periodTakenRetryMinutes = []int{1, 5}

// releaseRetryMinutes is Python RELEASE_RETRY_MINUTES (1173): a released row waits this long.
var releaseRetryMinutes = map[string]int{
	"not_eligible": 15,
	"no_account":   15,
	"bad_window":   60,
}

// Pin states returned by the revoke-side lookup (1155). Declared here because they are
// Python module constants; the revoke phase uses them.
const (
	PinPresent = "present"
	PinGone    = "gone"
	PinUnknown = "unknown"
	// LookupFailed is stored as lookup_failed:<n> in last_error.
	LookupFailed   = "lookup_failed"
	LookupMaxTries = 3
)

// ambiguousDeleteErrors are last_error values that leave a delete's result unknown.
var ambiguousDeleteErrors = []string{"", "network", "transient", LookupFailed, ttlock.KindCodeMissing}

// gatewayRetryKinds are TTLock error kinds the gateway may retry (GATEWAY_RETRY_KINDS).
var gatewayRetryKinds = []string{
	ttlock.KindOffline, ttlock.KindTransient, ttlock.KindNetwork, ttlock.KindRate,
	ttlock.KindBudget, ttlock.KindCodeMissing, ttlock.KindLockSetup,
}

// Keys of the mail payload that the code mail carries (App/app/mail.py DOOR_CODE_KEY, QR_SPAYD_KEY).
const (
	doorCodePayloadKey = "door_code_enc"
	qrSpaydPayloadKey  = "qr_spayd"
)

// Completion actions of CompletionDoorCode.
const (
	CompletionHold    = "hold"
	CompletionWith    = "with"
	CompletionWithout = "without"
)

// Release reasons and the alert kind shared by issue.
const (
	alertDoorCodeFailed = "door_code_failed"
	alertFailedMessage  = "Door code could not be created"
)
