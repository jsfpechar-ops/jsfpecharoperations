package guesthandoff

// Ports guest_handoff.on_new_question, refresh_alert and open_counts (brief 0351).

import (
	"context"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/hostweb"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/mail"
	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport"
)

const (
	AlertKind = "guest_question"
	MailKind  = "guest_question"
)

// OnNewQuestion is guest_handoff.on_new_question. Never panics; errors are logged.
func OnNewQuestion(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, questionID int64) {
	defer func() {
		if r := recover(); r != nil {
			log.Printf("guesthandoff: question %d: panic %v", questionID, r)
		}
	}()
	var aptID int64
	var urgent int
	err := pool.QueryRow(ctx, `SELECT apartment_id, COALESCE(urgent,0) FROM guest_question WHERE id = $1`, questionID).Scan(&aptID, &urgent)
	if errors.Is(err, pgx.ErrNoRows) {
		return
	}
	if err != nil {
		log.Printf("guesthandoff: question %d: %v", questionID, err)
		return
	}
	count, err := RefreshAlert(ctx, pool, getenv, now, aptID)
	if err != nil {
		log.Printf("guesthandoff: question %d refresh: %v", questionID, err)
		return
	}
	_, urgentOpen, err := OpenCounts(ctx, pool, aptID)
	if err != nil {
		log.Printf("guesthandoff: question %d counts: %v", questionID, err)
		return
	}
	if count != 1 && !(urgent != 0 && urgentOpen == 1) {
		log.Printf("guest question %d apartment=%d open=%d (batch mail already sent)", questionID, aptID, count)
		return
	}
	var name string
	var legalEntityID, ownerID *int64
	err = pool.QueryRow(ctx, `SELECT COALESCE(internal_name,''), legal_entity_id, owner_user_id FROM apartment WHERE id = $1`, aptID).
		Scan(&name, &legalEntityID, &ownerID)
	if err != nil {
		log.Printf("guesthandoff: question %d property: %v", questionID, err)
		return
	}
	to := ""
	if legalEntityID != nil {
		to, err = entityContactEmail(ctx, pool, *legalEntityID)
		if err != nil {
			log.Printf("guesthandoff: question %d email: %v", questionID, err)
			return
		}
	}
	if to == "" {
		log.Printf("guest question %d apartment=%d: no host address, alert only", questionID, aptID)
		return
	}
	if !mailEnabled(getenv) {
		return
	}
	url := hostweb.AppBase(getenv) + questionsURL(aptID)
	content := mail.BuildGuestQuestionHostMail(hostweb.PublicBase(getenv), name, url)
	key := fmt.Sprintf("%s:%d:%d", MailKind, aptID, questionID)
	owner := int64(0)
	if ownerID != nil {
		owner = *ownerID
	}
	apt := aptID
	_, err = ubyport.EnqueueMail(ctx, pool, ubyport.OutboxMail{
		Kind:        MailKind,
		Key:         key,
		ApartmentID: &apt,
		OwnerUserID: &owner,
		To:          to,
		Subject:     content.Subject,
		Text:        content.Text,
		HTML:        content.HTML,
		Payload:     "",
	})
	if err != nil {
		log.Printf("guesthandoff: question %d enqueue: %v", questionID, err)
		return
	}
	log.Printf("guest question %d apartment=%d: host mailed", questionID, aptID)
}

func questionsURL(apartmentID int64) string {
	return fmt.Sprintf("/apartments/%d/guide/questions", apartmentID)
}

func entityContactEmail(ctx context.Context, pool *pgxpool.Pool, legalEntityID int64) (string, error) {
	var raw string
	err := pool.QueryRow(ctx, `SELECT COALESCE(contact_email,'') FROM legal_entity WHERE id = $1`, legalEntityID).Scan(&raw)
	if errors.Is(err, pgx.ErrNoRows) {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	return ubyport.NormaliseEmail(raw), nil
}

// OpenCounts is guest_handoff.open_counts: (open rows, open urgent rows).
func OpenCounts(ctx context.Context, pool *pgxpool.Pool, apartmentID int64) (open int, urgentOpen int, err error) {
	err = pool.QueryRow(ctx, `SELECT COUNT(*)::int, COALESCE(SUM(urgent),0)::int FROM guest_question WHERE apartment_id = $1 AND status = 'open'`, apartmentID).
		Scan(&open, &urgentOpen)
	return
}

// RefreshAlert is guest_handoff.refresh_alert via guest.handoffRefreshAlert rules.
func RefreshAlert(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string, now func() time.Time, apt int64) (int, error) {
	_ = getenv
	_ = now
	open, urgent, err := OpenCounts(ctx, pool, apt)
	if err != nil {
		return 0, err
	}
	key := dedupeKey(apt)
	if open == 0 {
		return 0, ubyport.ResolveAlert(ctx, pool, key)
	}
	var name string
	if err := pool.QueryRow(ctx, `SELECT COALESCE(internal_name,'') FROM apartment WHERE id = $1`, apt).Scan(&name); err != nil {
		return 0, err
	}
	msg := fmt.Sprintf("%d guest question(s) wait for an answer at %s", open, name)
	if urgent > 0 {
		msg += fmt.Sprintf(" (%d urgent)", urgent)
	}
	detail := "Leon (AI) could not answer from the guide. Answer in the app; the guest sees it on the guide page."
	level := "warning"
	if urgent > 0 {
		level = "critical"
	}
	variant := ""
	if urgent > 0 {
		variant = "urgent"
	}
	aptID := apt
	params := ubyport.AlertParams{"property": name, "count": open, "urgent": urgent, "variant": variant}
	err = ubyport.RaiseAlert(ctx, pool, level, AlertKind, msg, detail, key, &aptID, nil, nil, params)
	return open, err
}

func dedupeKey(apartmentID int64) string {
	return fmt.Sprintf("%s:%d", AlertKind, apartmentID)
}

func mailEnabled(getenv func(string) string) bool {
	b := strings.ToLower(strings.TrimSpace(getenv("UBYHOST_MAIL_BACKEND")))
	return b == "console" || b == "ses"
}
