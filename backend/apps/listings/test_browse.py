from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.escrow.models import Transaction

from .models import Listing, ListingPhoto
from .testing import make_listing, make_tx, make_user

Approval = Listing.Approval


class BrowseTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()  # signed out: browse is public
        self.seller = make_user("+2348031234567", first_name="Tolu", last_name="adeyemi", avatar_color="sky")
        self.buyer = make_user("+2348031111111")
        now = timezone.now()

        def live(title, **extra):
            listing = make_listing(self.seller, title=title, **extra)
            return listing

        self.phone = live("iPhone 12", category_slug="phones-tablets", price=240_000, state="lagos", area="Yaba", condition="good")
        self.ps5 = live("PS5 Slim", category_slug="gaming", price=280_000, state="lagos", area="Ikeja", condition="like_new")
        self.fridge = live("Samsung fridge", category_slug="home-appliances", price=185_000, state="lagos", area="Surulere")
        self.macbook = live("MacBook Air", category_slug="laptops-computers", price=520_000, state="fct", area="Wuse", condition="like_new")
        self.stroller = live("Baby stroller", category_slug="baby-kids", price=38_000, state="rivers", area="GRA", condition="fair")
        # Oldest first so "newest" order is predictable.
        for i, listing in enumerate([self.phone, self.ps5, self.fridge, self.macbook, self.stroller]):
            Listing.objects.filter(pk=listing.pk).update(created_at=now - timedelta(hours=10 - i))
        ListingPhoto.objects.create(listing=self.phone, image="listings/2026/09/cover.webp", position=0)

        # Never public:
        make_listing(self.seller, title="Pending", state="lagos", approval=Approval.PENDING)
        make_listing(self.seller, title="Rejected", state="lagos", approval=Approval.REJECTED)
        make_listing(self.seller, title="Deleted", state="lagos", is_deleted=True)
        make_tx(make_listing(self.seller, title="Sold", state="lagos"), self.buyer, Transaction.Status.COMPLETED)
        make_tx(make_listing(self.seller, title="Escrow", state="lagos"), self.buyer, Transaction.Status.HELD)

    def titles(self, query=""):
        res = self.client.get(f"/api/listings/{query}")
        self.assertEqual(res.status_code, 200)
        return [item["title"] for item in res.json()["results"]]

    def test_only_live_listings_newest_first(self):
        self.assertEqual(self.titles(), ["Baby stroller", "MacBook Air", "Samsung fridge", "PS5 Slim", "iPhone 12"])

    def test_card_fields_and_no_private_data(self):
        item = next(i for i in self.client.get("/api/listings/").json()["results"] if i["title"] == "iPhone 12")
        self.assertEqual(
            set(item), {"id", "title", "price", "condition", "area", "state", "created_at", "cover_url", "seller"}
        )
        self.assertEqual(item["seller"], {"first_name": "Tolu", "last_initial": "A", "avatar_color": "sky"})
        self.assertEqual(item["cover_url"], "/media/listings/2026/09/cover.webp")
        self.assertNotIn(self.seller.phone, str(item))

    def test_each_filter(self):
        self.assertEqual(set(self.titles("?state=lagos")), {"iPhone 12", "PS5 Slim", "Samsung fridge"})
        self.assertEqual(self.titles("?area=SURU"), ["Samsung fridge"])  # case-insensitive contains
        self.assertEqual(self.titles("?category=gaming"), ["PS5 Slim"])
        self.assertEqual(set(self.titles("?condition=like_new,fair")), {"PS5 Slim", "MacBook Air", "Baby stroller"})
        self.assertEqual(set(self.titles("?min=240000")), {"iPhone 12", "PS5 Slim", "MacBook Air"})
        self.assertEqual(set(self.titles("?max=185000")), {"Samsung fridge", "Baby stroller"})

    def test_combined_filters(self):
        self.assertEqual(self.titles("?state=lagos&category=phones-tablets"), ["iPhone 12"])
        self.assertEqual(self.titles("?state=lagos&condition=like_new&min=250000"), ["PS5 Slim"])
        self.assertEqual(self.titles("?state=fct&category=phones-tablets"), [])

    def test_sorts(self):
        self.assertEqual(self.titles("?sort=price_asc")[0], "Baby stroller")
        self.assertEqual(self.titles("?sort=price_desc")[0], "MacBook Air")

    def test_malformed_values_are_ignored(self):
        self.assertEqual(len(self.titles("?min=abc&condition=shiny&sort=weird")), 5)

    def test_pagination_24(self):
        for n in range(25):
            make_listing(self.seller, title=f"Extra {n}")
        body = self.client.get("/api/listings/").json()
        self.assertEqual((body["count"], len(body["results"])), (30, 24))
        self.assertEqual(len(self.client.get("/api/listings/?page=2").json()["results"]), 6)

    def test_facets(self):
        body = self.client.get("/api/listings/facets/").json()
        self.assertEqual(body["total"], 5)
        self.assertEqual(body["states"][0], {"key": "lagos", "label": "Lagos", "count": 3})
        self.assertIn({"key": "fct", "label": "Abuja (FCT)", "count": 1}, body["states"])

        lagos = self.client.get("/api/listings/facets/?state=lagos").json()
        counts = {c["slug"]: c["count"] for c in lagos["categories"]}
        self.assertEqual(lagos["scoped_total"], 3)
        self.assertEqual((counts["phones-tablets"], counts["gaming"], counts["laptops-computers"]), (1, 1, 0))

    def test_facet_counts_match_results(self):
        for state, area in [("", ""), ("lagos", ""), ("lagos", "yaba"), ("fct", "")]:
            facets = self.client.get(f"/api/listings/facets/?state={state}&area={area}").json()
            for cat in facets["categories"]:
                res = self.client.get(f"/api/listings/?state={state}&area={area}&category={cat['slug']}").json()
                self.assertEqual(res["count"], cat["count"], (state, area, cat["slug"]))
            total = self.client.get(f"/api/listings/?state={state}&area={area}").json()["count"]
            self.assertEqual(total, facets["scoped_total"])

    def test_categories(self):
        body = self.client.get("/api/categories/").json()
        self.assertEqual(len(body), 12)
        self.assertEqual(body[0], {"slug": "phones-tablets", "label": "Phones & tablets"})
        self.assertEqual(body[-1]["slug"], "other")
