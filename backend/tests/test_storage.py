import pytest

from app.storage import fix_image_urls, slugify, validate_slug


class TestValidateSlug:
    def test_simple_valid_slug(self):
        assert validate_slug("my-recipe") == "my-recipe"

    def test_alphanumeric_slug(self):
        assert validate_slug("recipe123") == "recipe123"

    def test_slug_with_numbers(self):
        assert validate_slug("recette-du-7-juin") == "recette-du-7-juin"

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError):
            validate_slug("../secret")

    def test_slash_rejected(self):
        with pytest.raises(ValueError):
            validate_slug("foo/bar")

    def test_uppercase_rejected(self):
        with pytest.raises(ValueError):
            validate_slug("MyRecipe")

    def test_space_rejected(self):
        with pytest.raises(ValueError):
            validate_slug("my recipe")

    def test_starts_with_dash_rejected(self):
        with pytest.raises(ValueError):
            validate_slug("-bad-slug")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError):
            validate_slug("")

    def test_dot_rejected(self):
        with pytest.raises(ValueError):
            validate_slug("recipe.with.dots")


class TestSlugify:
    def test_simple_title(self):
        assert slugify("Ma Recette") == "ma-recette"

    def test_accented_chars_stripped(self):
        assert slugify("Recette française") == "recette-francaise"

    def test_multiple_spaces_become_one_dash(self):
        assert slugify("poulet   rôti") == "poulet-roti"

    def test_special_chars_removed(self):
        assert slugify("Crème brûlée!") == "creme-brulee"

    def test_leading_trailing_dashes_stripped(self):
        assert slugify("  -recette-  ") == "recette"

    def test_empty_or_only_special_chars_gives_default(self):
        assert slugify("!!!") == "recette"
        assert slugify("") == "recette"

    def test_numbers_preserved(self):
        assert slugify("Recette n°3") == "recette-n3"

    def test_underscores_become_dash(self):
        assert slugify("ma_recette") == "ma-recette"


class TestFixImageUrls:
    def test_replaces_relative_image_src(self):
        html = '<img src="images/photo.jpg">'
        result = fix_image_urls(html, "ma-recette")
        assert result == '<img src="/uploads/ma-recette/images/photo.jpg">'

    def test_no_change_for_absolute_url(self):
        html = '<img src="/already/absolute.jpg">'
        assert fix_image_urls(html, "ma-recette") == html

    def test_multiple_images_replaced(self):
        html = '<img src="images/a.jpg"><img src="images/b.png">'
        result = fix_image_urls(html, "slug")
        assert '/uploads/slug/images/a.jpg' in result
        assert '/uploads/slug/images/b.png' in result

    def test_no_images_unchanged(self):
        html = "<p>Pas d'image ici</p>"
        assert fix_image_urls(html, "slug") == html
