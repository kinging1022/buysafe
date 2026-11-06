"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/me/', include('apps.users.me_urls')),
    path('api/me/', include('apps.listings.urls')),
    path('api/', include('apps.listings.public_urls')),
    path('api/', include('apps.offers.urls')),
    path('api/', include('apps.payments.urls')),
    path('api/deals/', include('apps.deals.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/waitlist/', include('apps.waitlist.urls')),
]

# Uploaded listing photos. In production the web server serves MEDIA_ROOT.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
