"""Regression tests for the findings of the security audit.

Each test names the issue it guards against, so a future refactor that
reintroduces one of them fails here instead of in production.
"""

import pytest
from fastapi.testclient import TestClient

from app.auth import BCRYPT_MAX_BYTES, decode_token, hash_password, verify_password
from app.main import app
from app.storage import image_filename_for, save_image, sniff_image_mime
from app.validation import MAX_TAGS, normalize_tag, normalize_tags, parse_tags

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64


# ---------------------------------------------------------------------------
# Stored XSS through tag names
# ---------------------------------------------------------------------------


class TestTagNormalisation:
    """A tag used to land inside an onclick="" handler as a JS string literal."""

    @pytest.mark.parametrize(
        "payload",
        [
            "');document.title='PWNED';//",
            '");alert(1);//',
            "<script>alert(1)</script>",
            "tag' onmouseover='alert(1)",
            "javascript:alert(1)",
        ],
    )
    def test_quotes_and_brackets_are_stripped(self, payload):
        cleaned = normalize_tag(payload)
        for char in "'\"<>()/;&=:":
            assert char not in cleaned

    def test_accented_letters_survive(self):
        assert normalize_tag("  Bœuf Bourguignon  ") == "bœuf bourguignon"
        assert normalize_tag("plat-froid") == "plat-froid"

    def test_duplicates_removed_and_order_kept(self):
        assert normalize_tags(["Dessert", "dessert", "Plat"]) == ["dessert", "plat"]

    def test_tag_count_is_capped(self):
        assert len(normalize_tags([f"tag{i}" for i in range(100)])) == MAX_TAGS

    def test_tag_length_is_capped(self):
        assert len(normalize_tag("a" * 500)) <= 40

    def test_parse_tags_splits_the_form_field(self):
        assert parse_tags("Dessert, plat , ,sucré") == ["dessert", "plat", "sucré"]


# ---------------------------------------------------------------------------
# Upload validation
# ---------------------------------------------------------------------------


class TestImageSniffing:
    @pytest.mark.parametrize(
        "data,expected",
        [
            (PNG, "image/png"),
            (JPEG, "image/jpeg"),
            (GIF, "image/gif"),
            (b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 32, "image/webp"),
            (b"\x00\x00\x00\x20ftypavif" + b"\x00" * 32, "image/avif"),
            (b"<script>alert(1)</script>", None),
            (b"<?php system($_GET[0]); ?>" + b"\x00" * 64, None),
            (b"", None),
            (b"short", None),
        ],
    )
    def test_signature_decides(self, data, expected):
        assert sniff_image_mime(data) == expected

    def test_declared_extension_cannot_smuggle_a_script(self, tmp_path):
        """A .php upload carrying PNG bytes is stored with an image extension."""
        assert image_filename_for("shell.php", "image/png") == "shell.png"
        assert image_filename_for("shell.phtml", "image/jpeg") == "shell.jpg"
        assert image_filename_for("x.html", "image/gif") == "x.gif"

    def test_matching_extension_is_preserved(self):
        assert image_filename_for("photo.jpeg", "image/jpeg") == "photo.jpeg"
        assert image_filename_for("photo.JPG", "image/jpeg") == "photo.JPG"
        assert image_filename_for("photo.png", "image/png") == "photo.png"

    def test_save_image_rejects_non_images(self):
        with pytest.raises(ValueError):
            save_image("some-slug", "evil.png", b"<script>alert(1)</script>")


# ---------------------------------------------------------------------------
# Password handling
# ---------------------------------------------------------------------------


class TestPasswordLimits:
    def test_long_password_does_not_raise(self):
        """bcrypt >= 5 raises above 72 bytes; the truncation is explicit now."""
        hashed = hash_password("A" * 200)
        assert verify_password("A" * 200, hashed)

    def test_truncation_boundary_is_bcrypt_s_own(self):
        hashed = hash_password("A" * BCRYPT_MAX_BYTES)
        assert verify_password("A" * (BCRYPT_MAX_BYTES + 50), hashed)

    def test_wrong_password_still_fails(self):
        assert not verify_password("nope", hash_password("A" * 200))

    def test_malformed_hash_returns_false(self):
        assert not verify_password("whatever", "not-a-bcrypt-hash")


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------


class TestTokenVersion:
    def test_version_is_carried_in_the_token(self):
        from app.auth import create_access_token

        token = create_access_token({"sub": "1", "username": "a", "ver": 7})
        assert decode_token(token).token_version == 7

    def test_missing_version_defaults_to_zero(self):
        from app.auth import create_access_token

        token = create_access_token({"sub": "1", "username": "a"})
        assert decode_token(token).token_version == 0


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestResponseHeaders:
    def test_csp_forbids_inline_scripts(self, client):
        csp = client.get("/login").headers["content-security-policy"]
        assert "script-src 'self';" in csp
        assert "'unsafe-inline'" not in csp.split("style-src")[0]
        for directive in ("form-action 'self'", "base-uri 'self'", "object-src 'none'"):
            assert directive in csp

    def test_html_is_never_cached(self, client):
        assert client.get("/login").headers["cache-control"] == "no-store"

    def test_hsts_follows_cookie_secure(self, client):
        # The test suite runs with COOKIE_SECURE=false, i.e. plain HTTP.
        assert "strict-transport-security" not in client.get("/login").headers


class TestDocsAreClosed:
    @pytest.mark.parametrize("path", ["/api/docs", "/api/redoc", "/openapi.json"])
    def test_disabled_by_default(self, client, path):
        assert client.get(path).status_code == 404

    def test_healthz_is_public(self, client):
        assert client.get("/healthz").status_code == 200


class TestCsrf:
    def test_cross_origin_post_is_refused(self, client):
        r = client.post(
            "/login",
            data={"username": "a", "password": "b"},
            headers={"Origin": "https://evil.example.com"},
        )
        assert r.status_code == 403

    def test_same_host_different_port_is_refused(self, client):
        """SameSite=Lax ignores the port; the Origin check must not."""
        r = client.post(
            "/login",
            data={"username": "a", "password": "b"},
            headers={"Origin": "http://testserver:4444"},
        )
        assert r.status_code == 403

    def test_cross_site_fetch_metadata_is_refused(self, client):
        r = client.post(
            "/login",
            data={"username": "a", "password": "b"},
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        assert r.status_code == 403

    def test_same_origin_post_passes_through(self, client):
        r = client.post(
            "/login",
            data={"username": "ghost", "password": "wrong-password"},
            headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        )
        assert r.status_code == 401  # reached the handler, rejected on credentials

    def test_safe_methods_are_untouched(self, client):
        r = client.get("/login", headers={"Origin": "https://evil.example.com"})
        assert r.status_code == 200


class TestPaginationBounds:
    @pytest.mark.parametrize("page", ["-5", "0", "99999999999999999999", "abc"])
    def test_out_of_range_page_is_a_422_not_a_500(self, client, page):
        assert client.get(f"/?page={page}").status_code == 422
