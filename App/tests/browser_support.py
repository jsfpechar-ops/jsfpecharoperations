"""Shared browser launch configuration for real Chromium test runs."""
import os


def chromium_launch_kwargs() -> dict[str, str]:
    """Use an explicit system browser when configured; otherwise use Playwright's bundle."""
    executable_path = os.environ.get("UBYHOST_BROWSER_EXECUTABLE")
    return {"executable_path": executable_path} if executable_path else {}
