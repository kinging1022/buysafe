from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import PhoneVerification, User
from .phone import mask_phone, normalize_ng_phone

PHONE = "+2348031234567"
PASSWORD = "Safe2buy1"
FAKE_CODE = "000000"


def register_payload(**overrides):
    data = {
        "first_name": "Chiamaka",
        "last_name": "Okafor",
        "phone": "0803 123 4567",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
    }
    data.update(overrides)
    return data


@override_settings(OTP_SERVICE="fake")
class AuthFlowTests(TestCase):
    def setUp(self):
        cache.clear()  # throttles and send limits live in the cache
        self.client = APIClient(enforce_csrf_checks=False)

    def post(self, name, data):
        return self.client.post(f"/api/auth/{name}/", data, format="json")

    def register(self, **overrides):
        return self.post("register", register_payload(**overrides))

    def allow_next_send(self, phone=PHONE):
        cache.delete(f"otp:last-send:{phone}")

    # -- register → verify → authenticated ---------------------------------

    def test_register_verify_then_authenticated(self):
        res = self.register()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json(), {"masked_phone": "+234 803 ••• 4567", "resend_available_in": 60})

        user = User.objects.get(phone=PHONE)
        self.assertFalse(user.phone_verified)
        self.assertEqual(user.phone_verifications.count(), 1)

        # Not signed in yet.
        self.assertEqual(self.client.get("/api/me/").status_code, 403)

        res = self.post("verify-otp", {"phone": PHONE, "code": FAKE_CODE})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["masked_phone"], "+234 803 ••• 4567")
        self.assertNotIn("phone", res.json()["user"])  # the full number never leaves the server

        user.refresh_from_db()
        self.assertTrue(user.phone_verified)
        self.assertTrue(user.phone_verifications.get().used)

        me = self.client.get("/api/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["first_name"], "Chiamaka")

    def test_verification_row_never_holds_the_code(self):
        self.register()
        v = PhoneVerification.objects.get()
        self.assertNotIn(FAKE_CODE, [v.pin_id, v.phone])

    def test_register_field_errors(self):
        res = self.register(first_name="C", phone="12345", password="short", password_confirm="nope")
        self.assertEqual(res.status_code, 400)
        body = res.json()
        self.assertIn("first_name", body)
        self.assertEqual(body["phone"], ["Enter a valid Nigerian mobile number."])

        res = self.register(password="alllowercase", password_confirm="alllowercase")
        messages = res.json()["password"]
        self.assertIn("Password needs a number.", messages)
        self.assertIn("Password needs a capital letter.", messages)

        res = self.register(password_confirm="Safe2buy2")
        self.assertEqual(res.json()["password_confirm"], ["Passwords don’t match yet."])

    # -- re-registering ------------------------------------------------------

    def test_reregistering_unverified_phone_updates_and_resends(self):
        self.register()
        self.allow_next_send()
        res = self.register(first_name="Chi", last_name="Eze", password="NewPass9", password_confirm="NewPass9")
        self.assertEqual(res.status_code, 201)

        user = User.objects.get(phone=PHONE)
        self.assertEqual((user.first_name, user.last_name), ("Chi", "Eze"))
        self.assertTrue(user.check_password("NewPass9"))
        self.assertEqual(User.objects.count(), 1)
        # A fresh code was issued and the earlier one stopped working.
        self.assertEqual(user.phone_verifications.count(), 2)
        self.assertEqual(user.phone_verifications.filter(used=False).count(), 1)

    def test_registering_verified_phone_is_rejected(self):
        User.objects.create_user(PHONE, PASSWORD, first_name="A", last_name="B", phone_verified=True)
        res = self.register()
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.json(), {"phone": ["An account with this number already exists."], "code": "phone_taken"}
        )

    # -- verify: wrong / expired ---------------------------------------------

    def test_wrong_code_decrements_attempts_then_expires(self):
        self.register()
        res = self.post("verify-otp", {"phone": PHONE, "code": "123456"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {"code": "invalid_code", "attempts_left": 2})

        res = self.post("verify-otp", {"phone": PHONE, "code": "123456"})
        self.assertEqual(res.json(), {"code": "invalid_code", "attempts_left": 1})

        res = self.post("verify-otp", {"phone": PHONE, "code": "123456"})
        self.assertEqual(res.json()["code"], "expired")

        # Even the right code is refused once attempts are used up.
        res = self.post("verify-otp", {"phone": PHONE, "code": FAKE_CODE})
        self.assertEqual(res.json()["code"], "expired")
        self.assertFalse(User.objects.get(phone=PHONE).phone_verified)

    def test_expired_code(self):
        self.register()
        PhoneVerification.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        res = self.post("verify-otp", {"phone": PHONE, "code": FAKE_CODE})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "expired")

    # -- resend ----------------------------------------------------------------

    def test_resend_cooldown_returns_429(self):
        self.register()
        res = self.post("resend-otp", {"phone": PHONE})
        self.assertEqual(res.status_code, 429)
        self.assertTrue(1 <= res.json()["retry_after"] <= 60)

        self.allow_next_send()
        res = self.post("resend-otp", {"phone": PHONE})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"resend_available_in": 60})

    def test_resend_hourly_cap(self):
        self.register()  # send 1
        for _ in range(4):  # sends 2–5
            self.allow_next_send()
            self.assertEqual(self.post("resend-otp", {"phone": PHONE}).status_code, 200)
        self.allow_next_send()
        res = self.post("resend-otp", {"phone": PHONE})
        self.assertEqual(res.status_code, 429)
        self.assertGreater(res.json()["retry_after"], 60)

    def test_resend_for_unknown_number_looks_identical(self):
        res = self.post("resend-otp", {"phone": "0809 999 0000"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"resend_available_in": 60})
        self.assertEqual(self.post("resend-otp", {"phone": "0809 999 0000"}).status_code, 429)
        self.assertEqual(PhoneVerification.objects.count(), 0)

    # -- login -----------------------------------------------------------------

    def test_login_blocked_when_unverified_and_otp_resent(self):
        self.register()
        self.allow_next_send()
        res = self.post("login", {"phone": "803 123 4567", "password": PASSWORD})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(
            res.json(),
            {"code": "phone_unverified", "masked_phone": "+234 803 ••• 4567", "resend_available_in": 60},
        )
        self.assertEqual(PhoneVerification.objects.filter(phone=PHONE).count(), 2)
        self.assertEqual(self.client.get("/api/me/").status_code, 403)

    def test_login_success_for_verified_user(self):
        User.objects.create_user(PHONE, PASSWORD, first_name="A", last_name="B", phone_verified=True)
        res = self.post("login", {"phone": "+234 803 123 4567", "password": PASSWORD})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/me/").status_code, 200)

    def test_invalid_credentials_do_not_reveal_whether_user_exists(self):
        User.objects.create_user(PHONE, PASSWORD, first_name="A", last_name="B", phone_verified=True)
        wrong_password = self.post("login", {"phone": PHONE, "password": "Wrong123"})
        unknown_user = self.post("login", {"phone": "0809 999 0000", "password": "Wrong123"})
        garbage_phone = self.post("login", {"phone": "hello", "password": "Wrong123"})
        for res in (wrong_password, unknown_user, garbage_phone):
            self.assertEqual(res.status_code, 400)
            self.assertEqual(
                res.json(), {"code": "invalid_credentials", "detail": "Phone number or password is incorrect."}
            )

    def test_unverified_user_blocked_from_authenticated_api(self):
        user = User.objects.create_user(PHONE, PASSWORD, first_name="A", last_name="B")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/me/").status_code, 403)

    def test_csrf_is_enforced_on_auth_posts(self):
        client = APIClient(enforce_csrf_checks=True)
        res = client.post("/api/auth/login/", {"phone": PHONE, "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_otp_provider_failure_is_a_clean_503(self):
        from .services.otp import OtpSendError

        with mock.patch("apps.users.services.otp.FakeOtpService.send_otp", side_effect=OtpSendError("x")):
            res = self.register()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["code"], "otp_send_failed")


def verified_user(phone=PHONE, password=PASSWORD, **extra):
    return User.objects.create_user(phone, password, first_name="Tolu", last_name="Adeyemi", phone_verified=True, **extra)


class ProfileTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = verified_user()
        self.client = APIClient()
        self.client.force_login(self.user)

    def patch(self, data):
        return self.client.patch("/api/me/", data, format="json")

    def test_get_me(self):
        body = self.client.get("/api/me/").json()
        self.assertEqual(
            set(body),
            {"id", "first_name", "last_name", "masked_phone", "email", "state", "area", "bio", "avatar_color",
             "date_joined", "phone_verified"},
        )
        self.assertEqual(body["masked_phone"], "+234 803 ••• 4567")
        self.assertEqual(body["avatar_color"], "marigold")

    def test_patch_profile(self):
        res = self.patch({"first_name": "Tolu", "last_name": "Adé", "state": "lagos", "area": " Surulere ",
                          "bio": "Moving abroad.", "avatar_color": "lime"})
        self.assertEqual(res.status_code, 200, res.json())
        self.user.refresh_from_db()
        self.assertEqual((self.user.state, self.user.area, self.user.avatar_color), ("lagos", "Surulere", "lime"))
        self.assertEqual(res.json()["bio"], "Moving abroad.")

    def test_patch_cannot_change_phone(self):
        res = self.patch({"phone": "+2348099999999", "first_name": "Tolu"})
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, PHONE)

    def test_bio_limit(self):
        self.assertEqual(self.patch({"bio": "x" * 160}).status_code, 200)
        res = self.patch({"bio": "x" * 161})
        self.assertEqual(res.status_code, 400)
        self.assertIn("bio", res.json())

    def test_avatar_color_choices(self):
        for color in ["marigold", "lime", "sky", "coral", "paper"]:
            with self.subTest(color=color):
                self.assertEqual(self.patch({"avatar_color": color}).status_code, 200)
        res = self.patch({"avatar_color": "#F5B82E"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("avatar_color", res.json())

    def test_field_rules(self):
        res = self.patch({"first_name": "T", "state": "atlantis", "area": "S"})
        self.assertEqual(set(res.json()), {"first_name", "state", "area"})
        self.assertEqual(self.patch({"area": ""}).status_code, 200)  # area is optional

    def test_requires_login(self):
        self.assertEqual(APIClient().get("/api/me/").status_code, 403)


class ChangePasswordTests(TestCase):
    NEW = "Newsafe24"

    def setUp(self):
        cache.clear()
        self.user = verified_user()
        self.client = APIClient()
        self.client.force_login(self.user)

    def change(self, current=PASSWORD, new=NEW, confirm=None, client=None):
        return (client or self.client).post(
            "/api/me/password/",
            {"current_password": current, "new_password": new, "new_password_confirm": confirm or new},
            format="json",
        )

    def test_wrong_current_password(self):
        res = self.change(current="Wrong1234")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["current_password"], ["That’s not your current password."])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_same_as_old_rejected(self):
        res = self.change(new=PASSWORD)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "password_unchanged")

    def test_new_password_rules_and_match(self):
        body = self.change(new="short", confirm="other").json()
        self.assertIn("new_password", body)
        self.assertEqual(body["new_password_confirm"], ["Passwords don’t match yet."])

    def test_success_signs_out_other_sessions_but_keeps_this_one(self):
        other = APIClient()
        other.force_login(self.user)
        self.assertEqual(other.get("/api/me/").status_code, 200)
        old_key = self.client.session.session_key

        res = self.change()
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.NEW))

        self.assertEqual(self.client.get("/api/me/").status_code, 200)
        self.assertNotEqual(self.client.session.session_key, old_key)  # fresh session for this device
        self.assertEqual(other.get("/api/me/").status_code, 403)


@override_settings(OTP_SERVICE="fake")
class PasswordResetTests(TestCase):
    NEW = "Newsafe24"

    def setUp(self):
        cache.clear()
        self.user = verified_user()
        self.client = APIClient()

    def post(self, step, data):
        return self.client.post(f"/api/auth/password-reset/{step}/", data, format="json")

    def get_token(self):
        self.assertEqual(self.post("request", {"phone": PHONE}).status_code, 200)
        res = self.post("verify", {"phone": PHONE, "code": FAKE_CODE})
        self.assertEqual(res.status_code, 200, res.json())
        return res.json()["reset_token"]

    def confirm(self, token, new=None):
        new = new or self.NEW
        return self.post("confirm", {"reset_token": token, "new_password": new, "new_password_confirm": new})

    def test_end_to_end(self):
        other = APIClient()
        other.force_login(self.user)

        res = self.post("request", {"phone": "0803 123 4567"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"masked_phone": "+234 803 ••• 4567", "resend_available_in": 60})
        verification = PhoneVerification.objects.get()
        self.assertEqual(verification.purpose, PhoneVerification.Purpose.PASSWORD_RESET)

        res = self.post("verify", {"phone": PHONE, "code": FAKE_CODE})
        token = res.json()["reset_token"]
        res = self.confirm(token)
        self.assertEqual(res.status_code, 204)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.NEW))
        self.assertEqual(other.get("/api/me/").status_code, 403)  # every session is signed out
        self.assertEqual(self.client.get("/api/me/").status_code, 403)  # and no auto-login
        login = self.client.post("/api/auth/login/", {"phone": PHONE, "password": self.NEW}, format="json")
        self.assertEqual(login.status_code, 200)

    def test_unknown_phone_gets_identical_response(self):
        known = self.post("request", {"phone": PHONE})
        unknown = self.post("request", {"phone": "0809 999 0000"})
        unverified = User.objects.create_user("+2348070000000", PASSWORD, first_name="A", last_name="B")
        not_verified = self.post("request", {"phone": unverified.phone})
        for res in (known, unknown, not_verified):
            self.assertEqual(res.status_code, 200)
            self.assertEqual(set(res.json()), {"masked_phone", "resend_available_in"})
            self.assertEqual(res.json()["resend_available_in"], 60)
        self.assertEqual(PhoneVerification.objects.count(), 1)

        # The cooldown applies to every number alike.
        for phone in (PHONE, "0809 999 0000"):
            again = self.post("request", {"phone": phone})
            self.assertEqual(again.status_code, 200)
            self.assertTrue(1 <= again.json()["resend_available_in"] <= 60)

    def test_wrong_code_uses_signup_error_shapes(self):
        self.post("request", {"phone": PHONE})
        res = self.post("verify", {"phone": PHONE, "code": "123456"})
        self.assertEqual(res.json(), {"code": "invalid_code", "attempts_left": 2})
        res = self.post("verify", {"phone": "0809 999 0000", "code": FAKE_CODE})
        self.assertEqual(res.json()["code"], "expired")

    def test_signup_code_cannot_be_used_for_reset(self):
        unverified = User.objects.create_user("+2348070000000", PASSWORD, first_name="A", last_name="B")
        from .services.verification import issue_code

        issue_code(unverified)  # a sign-up code
        res = self.post("verify", {"phone": unverified.phone, "code": FAKE_CODE})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "expired")

        issue_code(self.user)  # a sign-up code for a verified user's number
        res = self.post("verify", {"phone": PHONE, "code": FAKE_CODE})
        self.assertEqual(res.json()["code"], "expired")

    def test_reset_code_cannot_verify_signup(self):
        self.post("request", {"phone": PHONE})
        res = self.client.post("/api/auth/verify-otp/", {"phone": PHONE, "code": FAKE_CODE}, format="json")
        self.assertEqual(res.json()["code"], "expired")

    def test_token_is_single_use(self):
        token = self.get_token()
        self.assertEqual(self.confirm(token).status_code, 204)
        res = self.confirm(token, "Another99")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "reset_token_invalid")

    def test_expired_token_rejected(self):
        token = self.get_token()
        with mock.patch("django.core.signing.time.time", return_value=__import__("time").time() + 601):
            res = self.confirm(token)
        self.assertEqual(res.json()["code"], "reset_token_invalid")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_tampered_token_rejected(self):
        token = self.get_token()
        self.assertEqual(self.confirm(token[:-2] + "xx").json()["code"], "reset_token_invalid")
        self.assertEqual(self.confirm("nonsense").json()["code"], "reset_token_invalid")

    def test_confirm_validates_password(self):
        token = self.get_token()
        body = self.post("confirm", {"reset_token": token, "new_password": "short", "new_password_confirm": "x"}).json()
        self.assertIn("new_password", body)
        self.assertIn("new_password_confirm", body)
        self.assertEqual(self.confirm(token).status_code, 204)  # still usable after a validation error


class PhoneNormalisationTests(SimpleTestCase):
    def test_accepted_formats(self):
        for raw in [
            "08031234567",
            "8031234567",
            "+2348031234567",
            "2348031234567",
            "0803 123 4567",
            "+234 803 123 4567",
            "(0803) 123-4567",
            "0703.123.4567",
            "09031234567",
        ]:
            with self.subTest(raw=raw):
                self.assertRegex(normalize_ng_phone(raw), r"^\+234[789]\d{9}$")
        self.assertEqual(normalize_ng_phone("0803 123 4567"), "+2348031234567")

    def test_rejected_formats(self):
        for raw in ["", None, "12345", "06031234567", "080312345678", "+44 7700 900123", "0803123456a", "234803123456"]:
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                normalize_ng_phone(raw)

    def test_mask(self):
        self.assertEqual(mask_phone("+2348031234567"), "+234 803 ••• 4567")
