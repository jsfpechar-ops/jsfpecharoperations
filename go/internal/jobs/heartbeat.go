package jobs

import (
	"context"
	"log/slog"
	"net/http"
	"time"
)

// heartbeatClient bounds each dead-man ping to 5 s, as App/app/scheduler.py does.
var heartbeatClient = &http.Client{Timeout: 5 * time.Second}

// Ping GETs an external dead-man URL after a successful job run. An empty URL
// means "not configured" and makes no request. A failure is logged with the job
// name only (the URL may carry a secret) and never reaches the caller.
func Ping(ctx context.Context, url, job string) {
	if url == "" {
		return
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		slog.Warn("heartbeat ping failed", "job", job)
		return
	}
	resp, err := heartbeatClient.Do(req)
	if err != nil {
		slog.Warn("heartbeat ping failed", "job", job)
		return
	}
	resp.Body.Close()
}
