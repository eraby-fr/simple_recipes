import pytest
from pydantic import ValidationError

from app.schemas import RecipeCreate, RecipeUpdate, UserCreate


class TestUserCreate:
    def test_valid(self):
        u = UserCreate(username="alice", password="password123")
        assert u.username == "alice"
        assert u.password == "password123"

    def test_username_stripped(self):
        u = UserCreate(username="  alice  ", password="password123")
        assert u.username == "alice"

    def test_username_too_short(self):
        with pytest.raises(ValidationError):
            UserCreate(username="ab", password="password123")

    def test_username_too_long(self):
        with pytest.raises(ValidationError):
            UserCreate(username="a" * 33, password="password123")

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            UserCreate(username="alice", password="short")

    def test_password_exactly_8_chars(self):
        u = UserCreate(username="alice", password="12345678")
        assert u.password == "12345678"


class TestRecipeCreate:
    def test_valid(self):
        r = RecipeCreate(title="Ma Recette", content="Étapes ici")
        assert r.title == "Ma Recette"
        assert r.summary == ""
        assert r.tags == []
        assert r.prep_time == ""
        assert r.servings == ""

    def test_title_stripped(self):
        r = RecipeCreate(title="  Soupe  ", content="test")
        assert r.title == "Soupe"

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            RecipeCreate(title="   ", content="test")

    def test_tags_normalized_lowercase(self):
        r = RecipeCreate(title="Test", content="test", tags=["Pâtes", "ITALIEN"])
        assert r.tags == ["pâtes", "italien"]

    def test_tags_stripped_and_empty_filtered(self):
        r = RecipeCreate(title="Test", content="test", tags=["  soup  ", "", "  "])
        assert r.tags == ["soup"]

    def test_summary_optional(self):
        r = RecipeCreate(title="Test", content="test", summary="Un résumé")
        assert r.summary == "Un résumé"


class TestRecipeUpdate:
    def test_all_fields_optional(self):
        r = RecipeUpdate()
        assert r.title is None
        assert r.content is None
        assert r.summary is None
        assert r.tags is None

    def test_tags_normalized(self):
        r = RecipeUpdate(tags=["  SOUPE  ", "chaud"])
        assert r.tags == ["soupe", "chaud"]

    def test_tags_none_preserved(self):
        r = RecipeUpdate(tags=None)
        assert r.tags is None

    def test_partial_update(self):
        r = RecipeUpdate(title="Nouveau titre")
        assert r.title == "Nouveau titre"
        assert r.content is None
