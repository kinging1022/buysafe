from django.test import TestCase

from apps.users.models import User

from .models import Listing
from .testing import make_listing, make_user

Approval = Listing.Approval


class ListingReviewAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("+2348000000001", "Safe2buy1", first_name="Ada", last_name="Obi")
        self.client.force_login(self.admin)
        self.seller = make_user("+2348031234567")

    def change(self, listing, **overrides):
        data = {
            "approval_status": listing.approval_status,
            "rejection_reason": listing.rejection_reason,
            "seller": listing.seller_id,
            "title": listing.title,
            "category": listing.category_id,
            "condition": listing.condition,
            "description": listing.description,
            "price": listing.price,
            "state": listing.state,
            "area": listing.area,
            "photos-TOTAL_FORMS": 0,
            "photos-INITIAL_FORMS": 0,
            **overrides,
        }
        return self.client.post(f"/admin/listings/listing/{listing.pk}/change/", data)

    def test_queue_opens_on_pending(self):
        make_listing(self.seller, Approval.PENDING, title="Waiting")
        make_listing(self.seller, Approval.APPROVED, title="Already live")
        page = self.client.get("/admin/listings/listing/").content.decode()
        self.assertIn("Waiting", page)
        self.assertNotIn("Already live", page)
        self.assertIn("Already live", self.client.get("/admin/listings/listing/?approval=all").content.decode())

    def test_reject_needs_a_reason(self):
        listing = make_listing(self.seller, Approval.PENDING)
        res = self.change(listing, approval_status=Approval.REJECTED, rejection_reason="  ")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Tell the seller why it was rejected")
        listing.refresh_from_db()
        self.assertEqual(listing.approval_status, Approval.PENDING)

    def test_reject_with_reason(self):
        listing = make_listing(self.seller, Approval.PENDING)
        res = self.change(listing, approval_status=Approval.REJECTED, rejection_reason="Photos are blurry.")
        self.assertEqual(res.status_code, 302)
        listing.refresh_from_db()
        self.assertEqual(listing.approval_status, Approval.REJECTED)
        self.assertEqual(listing.rejection_reason, "Photos are blurry.")

    def test_approving_clears_old_reason(self):
        listing = make_listing(self.seller, Approval.REJECTED, rejection_reason="Photos are blurry.")
        self.change(listing, approval_status=Approval.APPROVED)
        listing.refresh_from_db()
        self.assertEqual(listing.approval_status, Approval.APPROVED)
        self.assertEqual(listing.rejection_reason, "")

    def test_bulk_approve(self):
        a = make_listing(self.seller, Approval.PENDING, title="A")
        b = make_listing(self.seller, Approval.REJECTED, title="B", rejection_reason="Wrong category.")
        self.client.post(
            "/admin/listings/listing/?approval=all",
            {"action": "approve", "_selected_action": [a.pk, b.pk]},
        )
        for listing in (a, b):
            listing.refresh_from_db()
            self.assertEqual(listing.approval_status, Approval.APPROVED)
            self.assertEqual(listing.rejection_reason, "")
