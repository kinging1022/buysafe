import csv

from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone

from apps.users.states import NG_STATES

from .models import WaitlistSignup
from .phone import normalize_waitlist_phone

CSV_FIELDS = [
    'phone', 'state', 'role', 'source', 'utm_source', 'utm_medium', 'utm_campaign',
    'created_at', 'updated_at', 'notified_at',
]
STATE_LABELS = dict(NG_STATES)


class NotifiedFilter(admin.SimpleListFilter):
    title = 'notified'
    parameter_name = 'notified'

    def lookups(self, request, model_admin):
        return [('yes', 'Yes'), ('no', 'No')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(notified_at__isnull=False)
        if self.value() == 'no':
            return queryset.filter(notified_at__isnull=True)
        return queryset


@admin.register(WaitlistSignup)
class WaitlistSignupAdmin(admin.ModelAdmin):
    list_display = ['phone', 'state', 'role', 'created_at']
    list_filter = ['state', 'role', NotifiedFilter]
    search_fields = ['phone']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['export_csv']

    @admin.action(description='Export selected signups as CSV')
    def export_csv(self, request, queryset):
        stamp = timezone.now().strftime('%Y%m%d-%H%M')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="waitlist-{stamp}.csv"'
        writer = csv.writer(response)
        writer.writerow(CSV_FIELDS)
        for row in queryset.order_by('created_at').values_list(*CSV_FIELDS):
            writer.writerow(row)
        return response

    def get_search_results(self, request, queryset, search_term):
        # Staff can search "0803 123 4567" etc. against the stored E.164 number.
        phone = normalize_waitlist_phone(search_term)
        if phone:
            return queryset.filter(phone=phone), False
        return super().get_search_results(request, queryset, search_term)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        try:
            qs = response.context_data['cl'].queryset
        except (AttributeError, KeyError):
            return response  # a redirect, or the CSV action's response
        rows = qs.order_by().values('state').annotate(n=Count('id')).order_by('-n', 'state')
        response.context_data['state_counts'] = [
            {'state': row['state'], 'label': STATE_LABELS.get(row['state'], row['state']), 'n': row['n']}
            for row in rows
        ]
        return response
