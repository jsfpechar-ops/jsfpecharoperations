package public

// Brief 1704b: operator.details() for the host pages that name the software
// provider (Settings > Help). Same environment reading as the legal pages.

// Operator is operator.details(): the UbyHost operator, not a host's entity.
type Operator struct {
	Name, ICO, DIC, Address, Email, RegistryURL string
}

// OperatorFromEnv reads the UBYHOST_OPERATOR_* variables as config.py does
// (the e-mail defaults to support@ubyhost.com).
func OperatorFromEnv(getenv func(string) string) Operator {
	c := loadConfig(getenv)
	return Operator{Name: c.OpName, ICO: c.OpICO, DIC: c.OpDIC, Address: c.OpAddress, Email: c.OpEmail, RegistryURL: c.OpRegistry}
}
