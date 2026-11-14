package authpage

// The Data values of the pages brief 1502 added. A later brief adds its own
// type in its own file.

// LoginData is login.html's context (admin_accounts.py login_form, again and
// _login_page_context).
type LoginData struct {
	Error                  string // a catalog key; "" shows no alert
	Email                  string // the typed address, as typed
	Next                   string // the hidden next field
	SkipTurnstile          bool   // a valid device cookie hides the widget
	StagingLoginEmail      string // staging only: the first admin's address
	StagingPasswordEnabled bool   // staging only: UBYHOST_STAGING_LOGIN_PASSWORD is set
	StagingAdminUsername   string // staging only: the first admin's login handle
}

// LoginSentData is login_sent.html's context.
type LoginSentData struct {
	Email              string
	Next               string
	Remember           bool
	DevLink            string // local development with console mail only
	StagingConsoleMail bool
}

// LoginLinkData is login_link.html's context.
type LoginLinkData struct {
	Expired bool
	Locked  bool
	Token   string
	Invite  bool
}

// TwoFactorLoginData is two_factor_login.html's context.
type TwoFactorLoginData struct {
	Pending string
	Error   string // a catalog key; "" shows no alert
}
