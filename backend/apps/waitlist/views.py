from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import WaitlistSignup
from .serializers import WaitlistSignupSerializer
from .throttles import WaitlistDailyThrottle

OK = {'ok': True}


class WaitlistSignupView(APIView):
    """POST /api/waitlist/ from the pre-launch page.

    Public JSON endpoint: no session authentication, so DRF doesn't enforce
    CSRF, and the throttles key on the client IP.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, WaitlistDailyThrottle]
    throttle_scope = 'waitlist'
    throttle_scope_daily = 'waitlist_day'

    def post(self, request):
        # Honeypot: people never see the `company` field. Bots get a normal reply.
        if str(request.data.get('company', '')).strip():
            return Response(OK)

        serializer = WaitlistSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        signup, created = WaitlistSignup.objects.get_or_create(phone=data['phone'], defaults=data)
        if not created:
            # Same reply for new and existing numbers, so nobody can check who's on the list.
            signup.state = data['state']
            signup.role = data['role']
            signup.save(update_fields=['state', 'role', 'updated_at'])
        return Response(OK)
