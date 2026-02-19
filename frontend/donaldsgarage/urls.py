"""
URL configuration for donaldsgarage project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic.base import TemplateView
from accounts.views import PrintRequestsView, PrintRequestNewView, PrintRequestDetailView, PrintRequestReturnView, ApiProxyView

urlpatterns = [
    path('admin/', admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("print-requests/", PrintRequestsView.as_view(), name="print-requests"),
    path("print-requests/new/", PrintRequestNewView.as_view(), name="print-request-new"),
    path("print-requests/<int:request_id>/", PrintRequestDetailView.as_view(), name="print-request-detail"),
    path("print-requests/<int:request_id>/return/", PrintRequestReturnView.as_view(), name="print-request-return"),
    # Proxy: forward all /api/... calls to Flask
    re_path(r"^api/(?P<path>.*)$", ApiProxyView.as_view(), name="api-proxy"),
]
