from app.main import route


def test_health():
    assert route("/health") == (200, "application/json", b'{"status": "ok"}')


def test_info_names_the_service():
    status, _, body = route("/")
    assert status == 200 and b'"service": "sample-api"' in body


def test_metrics_are_exposed():
    status, _, body = route("/metrics")
    assert status == 200 and b"http_requests_total" in body


def test_unknown_path_is_404():
    assert route("/nope")[0] == 404
