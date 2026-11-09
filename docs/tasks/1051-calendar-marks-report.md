# 1051 report

Status: done

Dashboard calendar strip: placeholders ("Reserved", "CLOSED - Not available") share one neutral label ("Booked"); the source shows as the Airbnb or Booking.com logo, named in the tooltip and aria-label; the green "guests complete" pill is gone; a stay covering today gets a quiet blue tint. Host blocks stay grey. Tests: new test_dashboard_overview_calendar_marks.py and calendar tests pass. Note: the overview calendar is hidden under 1024 px by design (app2.css), so 390/768 shots force it visible.
