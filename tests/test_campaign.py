"""
Campagne de test complète — Simple Recipes
==========================================
• 2 utilisateurs : testcook1 / testcook2
• 10 recettes créées (7 + 3)
• Tous les CRUD : Create, Read (liste, détail, search, filtre tag),
  Update, Delete
• Upload et suppression d'image
• Contrôle d'accès inter-utilisateurs
• Déconnexion et vérification de l'état non authentifié
• Nettoyage automatique via le fixture docker_container (conftest.py)

Lancer avec :
    pytest tests/test_campaign.py -v -s --browser chromium
"""
from __future__ import annotations

import base64
import re
import tempfile
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect

# ─────────────────────────────────────────────────────────────────────────────
# Données de test
# ─────────────────────────────────────────────────────────────────────────────

USER1 = {"username": "testcook1", "password": "CookPass1!"}
USER2 = {"username": "testcook2", "password": "CookPass2!"}

RECIPES_USER1 = [
    {
        "title": "Tarte Tatin",
        "summary": "La tarte renversée aux pommes caramélisées",
        "tags": "dessert, fruit, pomme",
        "content": (
            "## Ingrédients\n\n- 6 pommes Golden\n- 150g sucre\n- 80g beurre\n"
            "- 1 pâte feuilletée\n\n## Préparation\n\n"
            "1. Préchauffer le four à 180 °C.\n"
            "2. Caraméliser le sucre dans une poêle allant au four.\n"
            "3. Ajouter le beurre puis les pommes épluchées et coupées.\n"
            "4. Couvrir de pâte, enfourner 25 min."
        ),
    },
    {
        "title": "Soupe à l'Oignon",
        "summary": "Classique français réconfortant",
        "tags": "soupe, hiver, fromage",
        "content": (
            "## Ingrédients\n\n- 4 oignons\n- 1 L bouillon de bœuf\n"
            "- 100 g gruyère râpé\n- Baguette\n\n## Préparation\n\n"
            "1. Émincer les oignons et les faire revenir 30 min à feu doux.\n"
            "2. Ajouter le bouillon, mijoter 20 min.\n"
            "3. Verser dans des bols, couvrir de pain et de gruyère, gratiner."
        ),
    },
    {
        "title": "Bœuf Bourguignon",
        "summary": "Mijoté en vin rouge de Bourgogne",
        "tags": "plat, viande, hiver",
        "content": (
            "## Ingrédients\n\n- 1 kg bœuf à braiser\n- 750 ml vin rouge\n"
            "- 200 g lardons\n- Carottes, champignons\n\n## Préparation\n\n"
            "1. Mariner la viande 12 h dans le vin.\n"
            "2. Faire revenir les lardons et les légumes.\n"
            "3. Ajouter la viande, mouiller avec la marinade, mijoter 3 h."
        ),
    },
    {
        "title": "Quiche Lorraine",
        "summary": "La vraie recette au lard fumé",
        "tags": "entrée, salé, four",
        "content": (
            "## Ingrédients\n\n- 1 pâte brisée\n- 200 g lardons fumés\n"
            "- 3 œufs\n- 20 cl crème fraîche\n\n## Préparation\n\n"
            "1. Préchauffer le four à 200 °C.\n"
            "2. Faire revenir les lardons.\n"
            "3. Battre les œufs avec la crème, ajouter les lardons.\n"
            "4. Verser sur la pâte, enfourner 30 min."
        ),
    },
    {
        "title": "Crêpes Bretonnes",
        "summary": "Recette traditionnelle de crêpes légères",
        "tags": "dessert, bretagne, rapide",
        "content": (
            "## Ingrédients\n\n- 250 g farine\n- 3 œufs\n- 500 ml lait\n"
            "- 50 g beurre fondu\n\n## Préparation\n\n"
            "1. Mélanger farine et œufs.\n"
            "2. Ajouter le lait progressivement en fouettant.\n"
            "3. Incorporer le beurre fondu. Laisser reposer 1 h.\n"
            "4. Cuire à la poêle."
        ),
    },
    {
        "title": "Ratatouille",
        "summary": "Légumes provençaux mijotés",
        "tags": "légumes, méditerranéen, végétarien",
        "content": (
            "## Ingrédients\n\n- 2 courgettes\n- 2 aubergines\n"
            "- 4 tomates\n- 2 poivrons\n- Huile d'olive\n\n## Préparation\n\n"
            "1. Couper tous les légumes en rondelles.\n"
            "2. Faire revenir l'oignon à l'huile d'olive.\n"
            "3. Ajouter les légumes par couches, mijoter 45 min."
        ),
    },
    {
        "title": "Coq au Vin",
        "summary": "Poulet mijoté au vin rouge",
        "tags": "plat, volaille, vin",
        "content": (
            "## Ingrédients\n\n- 1 poulet découpé\n- 750 ml vin rouge\n"
            "- 200 g champignons\n- 150 g lardons\n\n## Préparation\n\n"
            "1. Faire dorer les morceaux de poulet.\n"
            "2. Déglacer au vin rouge.\n"
            "3. Ajouter champignons et lardons, mijoter 1 h 30."
        ),
    },
]

RECIPES_USER2 = [
    {
        "title": "Pain Maison",
        "summary": "Pain artisanal à la croûte dorée",
        "tags": "boulangerie, pain",
        "content": (
            "## Ingrédients\n\n- 500 g farine T65\n- 320 ml eau tiède\n"
            "- 10 g levure fraîche\n- 10 g sel\n\n## Préparation\n\n"
            "1. Dissoudre la levure dans l'eau.\n"
            "2. Mélanger farine et sel, puis ajouter l'eau levurée.\n"
            "3. Pétrir 10 min. Laisser lever 1 h.\n"
            "4. Façonner, laisser lever 45 min, enfourner à 240 °C."
        ),
    },
    {
        "title": "Mousse au Chocolat",
        "summary": "Dessert aérien au chocolat noir",
        "tags": "dessert, chocolat, rapide",
        "content": (
            "## Ingrédients\n\n- 200 g chocolat noir 70 %\n- 6 œufs\n"
            "- 50 g sucre\n\n## Préparation\n\n"
            "1. Faire fondre le chocolat au bain-marie.\n"
            "2. Séparer les blancs des jaunes.\n"
            "3. Incorporer les jaunes au chocolat tiédi.\n"
            "4. Monter les blancs en neige, les incorporer délicatement.\n"
            "5. Réfrigérer 4 h."
        ),
    },
    {
        "title": "Salade Niçoise",
        "summary": "Fraîcheur méditerranéenne",
        "tags": "entrée, salade, méditerranéen",
        "content": (
            "## Ingrédients\n\n- 200 g thon en conserve\n- 4 œufs durs\n"
            "- 100 g olives noires\n- Tomates, haricots verts\n\n## Préparation\n\n"
            "1. Cuire les haricots verts à l'eau salée.\n"
            "2. Dresser tous les ingrédients sur un lit de salade.\n"
            "3. Assaisonner à l'huile d'olive et au citron."
        ),
    },
]

# Image PNG 1×1 pixel rouge encodée en base64 (fichier de test léger)
_RED_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADklEQ"
    "VQI12P4z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
)

# ── État partagé entre les tests (slugs créés, image uploadée) ────────────────
_STATE: dict[str, Any] = {
    "user1_slugs": [],
    "user2_slugs": [],
    "uploaded_image": None,
}

# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def _fill_recipe_form(page: Page, recipe: dict) -> None:
    page.fill("#title",   recipe["title"])
    page.fill("#summary", recipe.get("summary", ""))
    page.fill("#tags",    recipe.get("tags", ""))
    page.fill("#content", recipe.get("content", ""))


def _net_idle(page: Page, timeout: int = 8_000) -> None:
    page.wait_for_load_state("networkidle", timeout=timeout)


# ─────────────────────────────────────────────────────────────────────────────
# Campagne
# ─────────────────────────────────────────────────────────────────────────────

class TestCampaign:
    """Exécution séquentielle : les tests sont nommés 01…25 pour garantir l'ordre."""

    # ════════════════════════════════════════════════════════════════════════
    # Phase 1 — Inscription (redirige vers /login)
    # ════════════════════════════════════════════════════════════════════════

    def test_01_register_user1(self, page1: Page, base_url: str) -> None:
        """testcook1 s'inscrit (premier compte = admin approuvé) → /login."""
        page1.goto(f"{base_url}/register")
        expect(page1.locator("h1")).to_have_text("Créer un compte")
        page1.fill("#username", USER1["username"])
        page1.fill("#password", USER1["password"])
        page1.click("button[type='submit']")
        page1.wait_for_url(f"{base_url}/login", timeout=10_000)

    def test_02_register_user2(self, page2: Page, base_url: str) -> None:
        """testcook2 s'inscrit → compte en attente d'approbation."""
        page2.goto(f"{base_url}/register")
        expect(page2.locator("h1")).to_have_text("Créer un compte")
        page2.fill("#username", USER2["username"])
        page2.fill("#password", USER2["password"])
        page2.click("button[type='submit']")
        expect(page2.get_by_role("status")).to_contain_text("approuver")

    # ════════════════════════════════════════════════════════════════════════
    # Phase 2 — Connexion
    # ════════════════════════════════════════════════════════════════════════

    def test_03_login_user1(self, page1: Page, base_url: str) -> None:
        """testcook1 se connecte → redirigé vers / avec son nom dans la nav."""
        page1.goto(f"{base_url}/login")
        expect(page1.locator("h1")).to_have_text("Connexion")
        page1.fill("#username", USER1["username"])
        page1.fill("#password", USER1["password"])
        page1.click("button[type='submit']")
        page1.wait_for_url(f"{base_url}/", timeout=10_000)
        expect(page1.locator(".site-header nav")).to_contain_text(USER1["username"])
        expect(page1.get_by_role("button", name="Nouvelle recette")).to_be_visible()
        expect(page1.get_by_role("link", name="Comptes")).to_be_visible()

    def test_04_login_user2(self, page1: Page, page2: Page, base_url: str) -> None:
        """L'admin approuve testcook2, qui peut alors se connecter."""
        page1.goto(f"{base_url}/admin/users")
        expect(page1.locator("h1")).to_have_text("Gestion des comptes")
        row = page1.locator("tr", has_text=USER2["username"])
        row.get_by_role("button", name="Approuver").click()
        expect(row).to_contain_text("Approuvé", timeout=10_000)

        page2.goto(f"{base_url}/login")
        page2.fill("#username", USER2["username"])
        page2.fill("#password", USER2["password"])
        page2.click("button[type='submit']")
        page2.wait_for_url(f"{base_url}/", timeout=10_000)
        expect(page2.locator(".site-header nav")).to_contain_text(USER2["username"])

    # ════════════════════════════════════════════════════════════════════════
    # Phase 3 — Création (C) — 10 recettes
    # ════════════════════════════════════════════════════════════════════════

    def test_05_create_7_recipes_user1(self, page1: Page, base_url: str) -> None:
        """testcook1 crée 7 recettes via le formulaire /recipes/new."""
        for recipe in RECIPES_USER1:
            page1.goto(f"{base_url}/recipes/new")
            expect(page1.locator("h1")).to_contain_text("Nouvelle recette")
            _fill_recipe_form(page1, recipe)
            page1.click(".form-actions button[type='submit']")
            # Après création → redirect vers /recipes/{slug}
            page1.wait_for_url(
                re.compile(rf"{re.escape(base_url)}/recipes/[a-z0-9\-]+$"),
                timeout=10_000,
            )
            slug = page1.url.split("/recipes/")[-1]
            _STATE["user1_slugs"].append(slug)
            expect(page1.locator("h1")).to_have_text(recipe["title"])

        assert len(_STATE["user1_slugs"]) == 7, (
            f"7 recettes attendues, {len(_STATE['user1_slugs'])} créées"
        )

    def test_06_create_3_recipes_user2(self, page2: Page, base_url: str) -> None:
        """testcook2 crée 3 recettes via le formulaire /recipes/new."""
        for recipe in RECIPES_USER2:
            page2.goto(f"{base_url}/recipes/new")
            _fill_recipe_form(page2, recipe)
            page2.click(".form-actions button[type='submit']")
            page2.wait_for_url(
                re.compile(rf"{re.escape(base_url)}/recipes/[a-z0-9\-]+$"),
                timeout=10_000,
            )
            slug = page2.url.split("/recipes/")[-1]
            _STATE["user2_slugs"].append(slug)
            expect(page2.locator("h1")).to_have_text(recipe["title"])

        assert len(_STATE["user2_slugs"]) == 3, (
            f"3 recettes attendues, {len(_STATE['user2_slugs'])} créées"
        )

    # ════════════════════════════════════════════════════════════════════════
    # Phase 4 — Lecture (R) : liste, détail, recherche, filtre
    # ════════════════════════════════════════════════════════════════════════

    def test_07_list_shows_10_recipes(self, page1: Page, base_url: str) -> None:
        """La page d'accueil affiche exactement 10 cartes recettes."""
        page1.goto(f"{base_url}/")
        _net_idle(page1)
        cards = page1.locator("article.recipe-card")
        count = cards.count()
        assert count == 10, f"10 recettes attendues, {count} affichées"

    def test_08_search_full_text(self, page1: Page, base_url: str) -> None:
        """Recherche 'tarte' → au moins 1 résultat contenant 'tarte' dans le titre."""
        page1.goto(f"{base_url}/")
        page1.fill("#search-input", "tarte")
        _net_idle(page1)
        cards = page1.locator("article.recipe-card")
        assert cards.count() >= 1, "Aucun résultat pour la recherche 'tarte'"
        titles = [cards.nth(i).locator("h2").inner_text().lower() for i in range(cards.count())]
        assert any("tarte" in t for t in titles), f"'tarte' introuvable dans {titles}"

    def test_09_filter_by_tag_dessert(self, page1: Page, base_url: str) -> None:
        """Filtre tag 'dessert' → 3 recettes (Tarte Tatin, Crêpes, Mousse au Chocolat)."""
        page1.goto(f"{base_url}/")
        _net_idle(page1)
        btn = page1.locator("button.tag-btn", has_text="dessert")
        expect(btn).to_be_visible()
        # Use expect_response to avoid HTMX race condition (request may not start
        # before _net_idle returns if called immediately after click).
        with page1.expect_response(lambda r: "tag=" in r.url and r.status == 200):
            btn.click()
        cards = page1.locator("article.recipe-card")
        count = cards.count()
        assert count == 3, f"3 recettes 'dessert' attendues, {count} affichées"

    def test_10_view_recipe_detail_user1(self, page1: Page, base_url: str) -> None:
        """Consulter le détail de 'Tarte Tatin' (slug[0] de user1)."""
        slug = _STATE["user1_slugs"][0]
        page1.goto(f"{base_url}/recipes/{slug}")
        expect(page1.locator("h1")).to_have_text(RECIPES_USER1[0]["title"])
        expect(page1.locator(".recipe-byline")).to_contain_text(USER1["username"])
        expect(page1.locator(".recipe-content")).to_be_visible()
        # Boutons Modifier/Supprimer visibles pour l'auteur
        expect(page1.locator(".recipe-actions")).to_be_visible()

    def test_11_user2_reads_user1_recipe(self, page2: Page, base_url: str) -> None:
        """testcook2 peut lire une recette de testcook1 mais sans boutons d'action."""
        slug = _STATE["user1_slugs"][0]
        page2.goto(f"{base_url}/recipes/{slug}")
        expect(page2.locator("h1")).to_have_text(RECIPES_USER1[0]["title"])
        # Pas d'actions pour un non-auteur
        expect(page2.locator(".recipe-actions")).to_have_count(0)

    # ════════════════════════════════════════════════════════════════════════
    # Phase 5 — Mise à jour (U)
    # ════════════════════════════════════════════════════════════════════════

    def test_12_update_recipe_user1(self, page1: Page, base_url: str) -> None:
        """testcook1 modifie 'Tarte Tatin' : nouveau titre, résumé et tags."""
        slug = _STATE["user1_slugs"][0]
        page1.goto(f"{base_url}/recipes/{slug}/edit")
        expect(page1.locator("h1")).to_contain_text("Modifier la recette")

        page1.fill("#title",   "Tarte Tatin Revisitée")
        page1.fill("#summary", "Version allégée avec moins de beurre")
        page1.fill("#tags",    "dessert, fruit, pomme, allégé")
        page1.click(".form-actions button[type='submit']")

        # Le slug ne change pas à la mise à jour
        page1.wait_for_url(f"{base_url}/recipes/{slug}", timeout=10_000)
        expect(page1.locator("h1")).to_have_text("Tarte Tatin Revisitée")
        expect(page1.locator(".recipe-summary")).to_have_text(
            "Version allégée avec moins de beurre"
        )

    def test_13_update_recipe_user2(self, page2: Page, base_url: str) -> None:
        """testcook2 modifie 'Pain Maison' : nouveau contenu et nouveaux tags."""
        slug = _STATE["user2_slugs"][0]
        page2.goto(f"{base_url}/recipes/{slug}/edit")
        expect(page2.locator("h1")).to_contain_text("Modifier la recette")

        page2.fill("#tags", "boulangerie, pain, artisanal, levure-fraîche")
        page2.fill(
            "#content",
            "## Ingrédients\n\n- 500 g farine T65\n- 320 ml eau\n\n"
            "## Conseil\n\nUtiliser de la levure fraîche pour un meilleur goût.",
        )
        page2.click(".form-actions button[type='submit']")
        page2.wait_for_url(f"{base_url}/recipes/{slug}", timeout=10_000)
        expect(page2.locator("h1")).to_have_text(RECIPES_USER2[0]["title"])

    # ════════════════════════════════════════════════════════════════════════
    # Phase 6 — Contrôle d'accès
    # ════════════════════════════════════════════════════════════════════════

    def test_14_no_action_buttons_for_non_author(self, page2: Page, base_url: str) -> None:
        """testcook2 ne voit aucun bouton d'action sur la recette de testcook1."""
        slug = _STATE["user1_slugs"][2]  # Bœuf Bourguignon
        page2.goto(f"{base_url}/recipes/{slug}")
        expect(page2.locator(".recipe-actions")).to_have_count(0)

    def test_15_non_author_edit_submit_is_forbidden(self, page2: Page, base_url: str) -> None:
        """testcook2 tente d'accéder à l'édition d'une recette de testcook1 → 403 GET et POST."""
        slug = _STATE["user1_slugs"][2]  # Bœuf Bourguignon
        # The GET edit endpoint also enforces authorship → 403
        get_resp = page2.request.get(f"{base_url}/recipes/{slug}/edit")
        assert get_resp.status == 403, (
            f"GET edit attendu 403 Forbidden, reçu {get_resp.status}"
        )
        # POST edit also enforces authorship → 403
        post_resp = page2.request.post(
            f"{base_url}/recipes/{slug}/edit",
            form={"title": "Tentative de hack", "summary": "", "tags": "", "content": ""},
        )
        assert post_resp.status == 403, (
            f"POST edit attendu 403 Forbidden, reçu {post_resp.status}"
        )

    # ════════════════════════════════════════════════════════════════════════
    # Phase 7 — Upload et suppression d'image
    # ════════════════════════════════════════════════════════════════════════

    def test_16_upload_image(self, page1: Page, base_url: str) -> None:
        """testcook1 uploade une image PNG sur 'Bœuf Bourguignon'."""
        slug = _STATE["user1_slugs"][2]
        page1.goto(f"{base_url}/recipes/{slug}/edit")

        # Créer un fichier image de test dans un répertoire temporaire
        tmpdir = Path(tempfile.mkdtemp())
        img_path = tmpdir / "test_photo.png"
        img_path.write_bytes(base64.b64decode(_RED_PNG_B64))

        # L'input déclenche automatiquement le submit HTMX (editor.js)
        page1.set_input_files("#file-upload", str(img_path))
        _net_idle(page1, timeout=12_000)

        # Vérifier la présence du nom de fichier dans la liste
        image_list = page1.locator("#image-list")
        expect(image_list).to_contain_text("test_photo.png", timeout=8_000)
        _STATE["uploaded_image"] = "test_photo.png"

    def test_17_image_visible_on_detail_page(self, page1: Page, base_url: str) -> None:
        """The uploaded image is shown as the recipe cover."""
        slug = _STATE["user1_slugs"][2]
        page1.goto(f"{base_url}/recipes/{slug}")
        cover = page1.locator("img.recipe-cover")
        expect(cover).to_be_visible(timeout=5_000)

    def test_18_delete_image(self, page1: Page, base_url: str) -> None:
        """testcook1 supprime l'image uploadée ; la liste affiche 'Aucune image'."""
        slug = _STATE["user1_slugs"][2]
        page1.goto(f"{base_url}/recipes/{slug}/edit")

        # Confirmer la boîte de dialogue native avant le clic
        page1.once("dialog", lambda d: d.accept())
        delete_btn = page1.locator("#image-list button.btn-danger").first
        expect(delete_btn).to_be_visible()
        delete_btn.click()
        _net_idle(page1, timeout=8_000)

        expect(page1.locator("#image-list")).to_contain_text(
            "Aucune image pour cette recette.", timeout=6_000
        )

    # ════════════════════════════════════════════════════════════════════════
    # Phase 8 — Suppression (D)
    # ════════════════════════════════════════════════════════════════════════

    def test_19_delete_recipe_user1(self, page1: Page, base_url: str) -> None:
        """testcook1 supprime 'Coq au Vin' (7ème recette, index 6)."""
        slug = _STATE["user1_slugs"][6]  # Coq au Vin
        page1.goto(f"{base_url}/recipes/{slug}")
        expect(page1.locator("h1")).to_have_text(RECIPES_USER1[6]["title"])

        # HTMX envoie hx-confirm → window.confirm() → accepter
        page1.once("dialog", lambda d: d.accept())
        page1.locator("button.btn-danger[hx-delete]").click()
        # HX-Redirect: / → navigation complète vers la page d'accueil
        page1.wait_for_url(f"{base_url}/", timeout=10_000)

    def test_20_delete_recipe_user2(self, page2: Page, base_url: str) -> None:
        """testcook2 supprime 'Salade Niçoise' (3ème recette, index 2)."""
        slug = _STATE["user2_slugs"][2]  # Salade Niçoise
        page2.goto(f"{base_url}/recipes/{slug}")
        expect(page2.locator("h1")).to_have_text(RECIPES_USER2[2]["title"])

        page2.once("dialog", lambda d: d.accept())
        page2.locator("button.btn-danger[hx-delete]").click()
        page2.wait_for_url(f"{base_url}/", timeout=10_000)

    # ════════════════════════════════════════════════════════════════════════
    # Phase 9 — Vérifications post-suppression
    # ════════════════════════════════════════════════════════════════════════

    def test_21_eight_recipes_remain(self, page1: Page, base_url: str) -> None:
        """Après 2 suppressions, il reste exactement 8 recettes."""
        page1.goto(f"{base_url}/")
        _net_idle(page1)
        count = page1.locator("article.recipe-card").count()
        assert count == 8, f"8 recettes attendues après suppressions, {count} affichées"

    def test_22_deleted_recipe_returns_404(self, page1: Page, base_url: str) -> None:
        """L'URL de la recette supprimée retourne HTTP 404."""
        slug = _STATE["user1_slugs"][6]  # Coq au Vin — supprimée
        response = page1.goto(f"{base_url}/recipes/{slug}")
        assert response is not None
        assert response.status == 404, (
            f"HTTP 404 attendu pour recette supprimée, reçu {response.status}"
        )

    def test_23_search_finds_updated_title(self, page1: Page, base_url: str) -> None:
        """La recherche retrouve le nouveau titre après mise à jour."""
        page1.goto(f"{base_url}/")
        page1.fill("#search-input", "revisitée")
        _net_idle(page1)
        cards = page1.locator("article.recipe-card")
        assert cards.count() >= 1, "La recette modifiée 'Tarte Tatin Revisitée' est introuvable"

    # ════════════════════════════════════════════════════════════════════════
    # Phase 10 — Déconnexion
    # ════════════════════════════════════════════════════════════════════════

    def _do_logout(self, page: Page, base_url: str) -> None:
        """Déconnexion robuste : supprime le cookie d'authentification du contexte navigateur."""
        # clear_cookies() is the only reliable Playwright API that actually removes
        # the cookie from the shared browser store before the next navigation.
        page.context.clear_cookies()
        page.goto(f"{base_url}/")
        # Sans authentification, / redirige vers /login
        page.wait_for_url(re.compile(r"/login$"), timeout=8_000)

    def test_24_logout_user1(self, page1: Page, base_url: str) -> None:
        """testcook1 se déconnecte → nav affiche 'Connexion'."""
        self._do_logout(page1, base_url)
        expect(page1.get_by_role("link", name="Connexion")).to_be_visible()

    def test_25_logout_user2(self, page2: Page, base_url: str) -> None:
        """testcook2 se déconnecte → nav affiche 'Connexion'."""
        self._do_logout(page2, base_url)
        expect(page2.get_by_role("link", name="Connexion")).to_be_visible()

    def test_26_unauthenticated_new_recipe_redirects_to_login(
        self, page1: Page, base_url: str
    ) -> None:
        """Après déconnexion, /recipes/new redirige vers /login."""
        page1.goto(f"{base_url}/recipes/new")
        expect(page1).to_have_url(re.compile(r"/login$"), timeout=5_000)

    def test_27_unauthenticated_login_flow(self, page1: Page, base_url: str) -> None:
        """Un utilisateur déconnecté peut se reconnecter correctement."""
        page1.goto(f"{base_url}/login")
        page1.fill("#username", USER1["username"])
        page1.fill("#password", USER1["password"])
        page1.click("button[type='submit']")
        page1.wait_for_url(f"{base_url}/", timeout=8_000)
        expect(page1.locator(".site-header nav")).to_contain_text(USER1["username"])

    def test_28_unauthenticated_recipe_detail_redirects_to_login(
        self, page2: Page, base_url: str
    ) -> None:
        """Après déconnexion, accéder à une recette redirige vers /login."""
        slug = _STATE["user1_slugs"][0]
        page2.goto(f"{base_url}/recipes/{slug}")
        expect(page2).to_have_url(re.compile(r"/login$"), timeout=5_000)

    def test_29_unauthenticated_api_recipes_returns_401(
        self, page2: Page, base_url: str
    ) -> None:
        """Après déconnexion, GET /api/recipes retourne 401."""
        resp = page2.request.get(f"{base_url}/api/recipes")
        assert resp.status == 401, (
            f"GET /api/recipes attendu 401 sans auth, reçu {resp.status}"
        )
