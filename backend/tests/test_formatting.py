from datetime import datetime
from uuid import uuid4

from app.formatting import format_date_fr
from app.storage import (
    gallery_filenames,
    get_cover_image_url,
    safe_image_filename,
    save_image,
    write_recipe_content,
)


def _slug() -> str:
    return f"t-{uuid4().hex[:10]}"


class TestSafeImageFilename:
    def test_keeps_simple_name(self):
        assert safe_image_filename("photo.jpg") == "photo.jpg"

    def test_strips_path_components(self):
        assert safe_image_filename("/tmp/sub/photo.png") == "photo.png"

    def test_replaces_spaces(self):
        assert safe_image_filename("my photo.jpg") == "my_photo.jpg"


class TestFormatDateFr:
    def test_datetime(self):
        assert format_date_fr(datetime(2026, 9, 15)) == "15 septembre 2026"

    def test_iso_string(self):
        assert format_date_fr("2022-05-10T00:00:00") == "10 mai 2022"

    def test_january(self):
        assert format_date_fr(datetime(2024, 1, 3)) == "3 janvier 2024"


class TestCoverAndGallery:
    def test_preferred_cover_used_when_present(self):
        slug = _slug()
        write_recipe_content(slug, "# Tatin")
        save_image(slug, "caramel.jpg", b"aaa")
        save_image(slug, "montage_pomme.jpg", b"bbb")
        url = get_cover_image_url(slug, "montage_pomme.jpg")
        assert url == f"/uploads/{slug}/images/montage_pomme.jpg"

    def test_cover_falls_back_to_first_sorted_name(self):
        slug = _slug()
        write_recipe_content(slug, "# x")
        save_image(slug, "z.jpg", b"z")
        save_image(slug, "a.jpg", b"a")
        url = get_cover_image_url(slug, "missing.jpg")
        assert url == f"/uploads/{slug}/images/a.jpg"

    def test_gallery_skips_cover_and_inline_markdown(self):
        slug = _slug()
        content = "Hello ![x](images/inline.jpg) more"
        write_recipe_content(slug, content)
        save_image(slug, "cover.jpg", b"c")
        save_image(slug, "inline.jpg", b"i")
        save_image(slug, "extra.jpg", b"e")
        names = gallery_filenames(slug, content, "cover.jpg")
        assert names == ["extra.jpg"]
