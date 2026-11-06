import shutil
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.escrow.models import Transaction

from .models import Listing, ListingPhoto
from .testing import image_file, make_listing, make_tx, make_user

MEDIA = tempfile.mkdtemp()
COLORS = ("#111111", "#777777", "#dddddd", "#aa3333", "#3333aa")


def payload(photos=3, **overrides):
    data = {
        "title": "Samsung fridge, 2 doors",
        "category": "home-appliances",
        "condition": "good",
        "description": "Bought in 2022, still cooling well. Small dent on the left door.",
        "price": "185000",
        "state": "lagos",
        "area": "Surulere",
        "photos": [image_file(f"p{i}.jpg", color=COLORS[i % len(COLORS)]) for i in range(photos)],
    }
    data.update(overrides)
    return data


@override_settings(MEDIA_ROOT=MEDIA)
class CreateListingTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.user = make_user("+2348031234567")
        self.client = APIClient()
        self.client.force_login(self.user)

    def post(self, data):
        return self.client.post("/api/listings/", data, format="multipart")

    def test_create(self):
        res = self.post(payload())
        self.assertEqual(res.status_code, 201, res.json())
        body = res.json()
        self.assertEqual(body["approval_status"], "pending")
        self.assertEqual(body["display_status"], "pending")
        self.assertEqual(body["fee"]["payout"], 166_500)
        self.assertEqual(len(body["photos"]), 3)
        listing = Listing.objects.get()
        self.assertEqual((listing.seller, listing.category.slug, listing.area_normalized), (self.user, "home-appliances", "surulere"))
        # Order kept: the first file is the cover.
        cover = Image.open(listing.photos.get(position=0).image.path)
        self.assertEqual(cover.format, "WEBP")
        self.assertEqual(cover.convert("RGB").getpixel((5, 5))[0], 0x11)

    def test_requires_verified_login(self):
        self.assertEqual(APIClient().post("/api/listings/", payload(), format="multipart").status_code, 403)
        unverified = make_user("+2348032222222")
        unverified.phone_verified = False
        unverified.save()
        client = APIClient()
        client.force_login(unverified)
        self.assertEqual(client.post("/api/listings/", payload(), format="multipart").status_code, 403)

    def test_field_rules(self):
        cases = {
            "title": ["Tv", "x" * 121],
            "category": ["", "cars"],
            "condition": ["", "mint"],
            "description": ["Too short", "x" * 1001],
            "price": ["", "1999", "50000001", "12.5"],
            "state": ["", "atlantis"],
            "area": ["", "S", "x" * 61],
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value[:20]):
                    res = self.post(payload(**{field: value}))
                    self.assertEqual(res.status_code, 400)
                    self.assertIn(field, res.json())
        self.assertEqual(self.post(payload(price="1999")).json()["price"], ["Minimum price is ₦2,000."])
        self.assertEqual(Listing.objects.count(), 0)

    def test_photo_count_3_to_5(self):
        self.assertEqual(self.post(payload(photos=2)).json()["photos"], ["Add at least 3 photos."])
        self.assertEqual(self.post(payload(photos=6)).json()["photos"], ["You can add up to 5 photos."])
        self.assertEqual(self.post(payload(photos=5)).status_code, 201)

    def test_bad_photo_saves_nothing(self):
        data = payload()
        data["photos"][1] = SimpleUploadedFile("fake.jpg", b"not an image at all", content_type="image/jpeg")
        res = self.post(data)
        self.assertEqual(res.json()["photos"], ["Use a JPG, PNG or WebP photo."])
        self.assertEqual((Listing.objects.count(), ListingPhoto.objects.count()), (0, 0))

    def test_photo_size_limit(self):
        from . import photos

        data = payload()
        original = photos.MAX_UPLOAD_BYTES
        photos.MAX_UPLOAD_BYTES = 100
        try:
            res = self.post(data)
        finally:
            photos.MAX_UPLOAD_BYTES = original
        self.assertEqual(res.json()["photos"], ["Each photo must be 10 MB or smaller."])

    def test_exif_and_gps_are_stripped_and_resized(self):
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"  # Make
        exif[0x8825] = {1: "N", 2: (6.0, 30.0, 0.0), 3: "E", 4: (3.0, 21.0, 0.0)}  # GPS: Lagos
        data = payload()
        data["photos"][0] = image_file("gps.jpg", size=(4000, 3000), exif=exif)
        self.assertIn(b"PhoneMaker", data["photos"][0].read())
        data["photos"][0].seek(0)

        self.assertEqual(self.post(data).status_code, 201)
        path = Listing.objects.get().photos.get(position=0).image.path
        stored = Image.open(path)
        self.assertEqual(max(stored.size), 2000)
        self.assertEqual(len(stored.getexif()), 0)
        self.assertNotIn("exif", stored.info)
        with open(path, "rb") as fh:
            raw = fh.read()
        self.assertNotIn(b"PhoneMaker", raw)
        self.assertNotIn(b"Exif", raw)


@override_settings(MEDIA_ROOT=MEDIA)
class EditListingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = make_user("+2348031234567")
        self.client = APIClient()
        self.client.force_login(self.owner)
        res = self.client.post("/api/listings/", payload(photos=4), format="multipart")
        self.listing = Listing.objects.get(pk=res.json()["id"])
        self.photo_ids = list(self.listing.photos.values_list("pk", flat=True))
        Listing.objects.filter(pk=self.listing.pk).update(approval_status="approved")

    def patch(self, data, client=None):
        return (client or self.client).patch(f"/api/listings/{self.listing.pk}/", data, format="multipart")

    def test_get_for_prefill(self):
        body = self.client.get(f"/api/listings/{self.listing.pk}/").json()["owner"]
        self.assertEqual(body["category"], "home-appliances")
        self.assertEqual([p["id"] for p in body["photos"]], self.photo_ids)

    def test_editing_approved_goes_back_to_pending(self):
        res = self.patch({"title": "Samsung fridge, double door"})
        self.assertEqual(res.status_code, 200, res.json())
        self.listing.refresh_from_db()
        self.assertEqual((self.listing.title, self.listing.approval_status), ("Samsung fridge, double door", "pending"))

    def test_resubmitting_rejected_clears_reason(self):
        Listing.objects.filter(pk=self.listing.pk).update(approval_status="rejected", rejection_reason="Too dark.")
        self.assertEqual(self.client.get(f"/api/listings/{self.listing.pk}/").json()["owner"]["rejection_reason"], "Too dark.")
        self.patch({"description": "New bright photos taken in daylight, works perfectly."})
        self.listing.refresh_from_db()
        self.assertEqual((self.listing.approval_status, self.listing.rejection_reason), ("pending", ""))

    def test_reorder_add_remove_photos(self):
        a, b, c, d = self.photo_ids
        res = self.patch({"photo_order": [f"p{c}", "n0", f"p{a}"], "new_photos": [image_file("new.png", fmt="PNG")]})
        self.assertEqual(res.status_code, 200, res.json())
        photos = list(self.listing.photos.order_by("position"))
        self.assertEqual([p.pk for p in photos][0], c)
        self.assertEqual(photos[2].pk, a)
        self.assertEqual(len(photos), 3)
        self.assertFalse(ListingPhoto.objects.filter(pk__in=[b, d]).exists())

    def test_photo_limits_on_edit(self):
        a, b, *_ = self.photo_ids
        self.assertEqual(self.patch({"photo_order": [f"p{a}", f"p{b}"]}).json()["photos"], ["Add at least 3 photos."])
        many = {"photo_order": [f"p{i}" for i in self.photo_ids] + ["n0", "n1"], "new_photos": [image_file(), image_file()]}
        self.assertEqual(self.patch(many).json()["photos"], ["You can add up to 5 photos."])

    def test_cannot_use_someone_elses_photo(self):
        other = make_listing(make_user("+2348033333333"))
        foreign = ListingPhoto.objects.create(listing=other, image="listings/x.webp", position=0)
        a, b, *_ = self.photo_ids
        res = self.patch({"photo_order": [f"p{a}", f"p{b}", f"p{foreign.pk}"]})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(ListingPhoto.objects.get(pk=foreign.pk).listing, other)

    def test_only_owner(self):
        stranger = APIClient()
        stranger.force_login(make_user("+2348034444444"))
        # Anyone can see the live listing, but not the owner's edit details.
        self.assertNotIn("owner", stranger.get(f"/api/listings/{self.listing.pk}/").json())
        self.assertEqual(self.patch({"title": "Mine now, thanks"}, client=stranger).status_code, 404)

    def test_not_editable_in_escrow_or_sold(self):
        buyer = make_user("+2348035555555")
        tx = make_tx(self.listing, buyer, Transaction.Status.HELD)
        self.assertEqual(self.patch({"title": "Changed title"}).status_code, 409)
        tx.status = Transaction.Status.COMPLETED
        tx.save()
        self.assertEqual(self.patch({"title": "Changed title"}).json()["code"], "not_editable")
