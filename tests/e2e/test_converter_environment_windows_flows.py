"""Environment converter page: the Time windows list (variable pull-down from the server, add/remove, server error)."""

from playwright.sync_api import expect

CSV = "timestamp,participant_id\n2025-01-15 10:30:00,P001\n"


def open_environment_tab(page, studio_url):
    page.goto(f"{studio_url}/converter")
    page.click("#environment-tab")
    expect(page.locator("#environment-panel")).to_be_visible()


def preview_file(page, tmp_path):
    data = tmp_path / "env.csv"
    data.write_text(CSV)
    page.set_input_files("#envDataFile", str(data))
    page.click("#envPreviewBtn")
    expect(page.locator("#envColumnMapping")).to_be_visible(timeout=30000)  # the windows list lives here


def test_window_rows_are_filled_from_the_server_and_can_be_removed(app_page, studio_url, tmp_path):
    open_environment_tab(app_page, studio_url)
    preview_file(app_page, tmp_path)

    app_page.click("#envAddWindowBtn")

    row = app_page.locator("#envWindowList .env-window-row")
    expect(row).to_have_count(1)
    expect(row.locator(".env-window-variable option[value='temp_c']")).to_have_count(1)
    expect(row.locator(".env-window-statistic option[value='max']")).to_have_count(1)
    row.locator(".env-window-remove").click()
    expect(row).to_have_count(0)


def test_bad_duration_shows_the_server_message_before_any_conversion(app_page, studio_url, tmp_path):
    app_page.allowed_http[400] = "/api/environment-convert-start"
    open_environment_tab(app_page, studio_url)
    preview_file(app_page, tmp_path)
    app_page.select_option("#envTimestampCol", "timestamp")
    app_page.select_option("#envParticipantCol", "participant_id")
    app_page.fill("#envLat", "47.07")
    app_page.fill("#envLon", "15.44")
    app_page.click("#envAddWindowBtn")
    app_page.fill("#envWindowList .env-window-duration", "3d")
    expect(app_page.locator("#envConvertBtn")).to_be_enabled()

    app_page.click("#envConvertBtn")

    expect(app_page.locator("#envError")).to_contain_text("is not an ISO 8601 duration such as P3D", timeout=15000)


def test_failed_window_options_route_shows_an_error_not_empty_pulldowns(app_page, studio_url, tmp_path):
    app_page.allowed_http[500] = "/api/environment-window-options"
    app_page.route(
        "**/api/environment-window-options",
        lambda route: route.fulfill(status=500, content_type="application/json", body='{"error": "boom"}'),
    )
    open_environment_tab(app_page, studio_url)
    preview_file(app_page, tmp_path)

    app_page.click("#envAddWindowBtn")

    expect(app_page.locator("#envError")).to_contain_text("Could not load the time window options")
    expect(app_page.locator("#envWindowList .env-window-row")).to_have_count(0)
