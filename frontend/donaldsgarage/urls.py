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
from accounts.views import PrintRequestsView, PrintRequestNewView, PrintRequestDetailView, PrintRequestReturnView, AdminStudentsView, ApiProxyView, WeeklyReportView, ReportSyncView, ReportRawView, PrinterDetailView, OperatorDetailView, MaterialsReportView, ErrorsReportView, MonthlyReportView

urlpatterns = [
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("print-requests/", PrintRequestsView.as_view(), name="print-requests"),
    path("print-requests/new/", PrintRequestNewView.as_view(), name="print-request-new"),
    path("print-requests/<int:request_id>/", PrintRequestDetailView.as_view(), name="print-request-detail"),
    path("print-requests/<int:request_id>/return/", PrintRequestReturnView.as_view(), name="print-request-return"),
    path("admin/students/", AdminStudentsView.as_view(), name="admin-students"),
    # Reports
    path("reports/weekly/",                    WeeklyReportView.as_view(),   name="weekly-report"),
    path("reports/sync/",                      ReportSyncView.as_view(),     name="report-sync"),
    path("reports/raw/",                       ReportRawView.as_view(),      name="report-raw"),
    path("reports/printer/<path:name>/",       PrinterDetailView.as_view(),  name="printer-detail"),
    path("reports/operator/<path:name>/",      OperatorDetailView.as_view(), name="operator-detail"),
    path("reports/materials/",                 MaterialsReportView.as_view(),name="materials-report"),
    path("reports/errors/",                    ErrorsReportView.as_view(),   name="errors-report"),
    path("reports/monthly/",                   MonthlyReportView.as_view(),  name="monthly-report"),
    path('admin/', admin.site.urls),
    # Proxy: forward all /api/... calls to Flask
    re_path(r"^api/(?P<path>.*)$", ApiProxyView.as_view(), name="api-proxy"),
]
