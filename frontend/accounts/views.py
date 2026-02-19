import requests as http_requests
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


FLASK_BASE = "http://localhost:5000"


class SignUpView(TemplateView):
    template_name = "registration/signup.html"


class PrintRequestsView(TemplateView):
    template_name = "print_requests.html"


class PrintRequestNewView(TemplateView):
    template_name = "print_request_new.html"


class PrintRequestDetailView(TemplateView):
    template_name = "print_request_detail.html"


class PrintRequestReturnView(TemplateView):
    template_name = "print_request_return.html"


@method_decorator(csrf_exempt, name='dispatch')
class ApiProxyView(View):
    """Forward every /api/... request to the Flask backend transparently."""

    http_method_names = ["get", "post", "put", "patch", "delete", "options"]

    def dispatch(self, request, path, *args, **kwargs):
        url = f"{FLASK_BASE}/api/{path}"

        # Forward headers (strip host and content-length — requests recalculates it)
        forward_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")
        }

        content_type = request.headers.get("Content-Type", "")

        if "multipart/form-data" in content_type:
            # File upload: forward files + POST fields separately so requests
            # rebuilds the multipart body with the correct boundary
            files = {
                name: (f.name, f.read(), f.content_type)
                for name, f in request.FILES.items()
            }
            # Strip Content-Type so requests sets its own boundary
            forward_headers.pop("Content-Type", None)
            resp = http_requests.request(
                method=request.method,
                url=url,
                headers=forward_headers,
                files=files,
                data=request.POST,
                params=request.GET,
                timeout=30,
            )
        else:
            resp = http_requests.request(
                method=request.method,
                url=url,
                headers=forward_headers,
                data=request.body,
                params=request.GET,
                timeout=15,
            )

        django_resp = HttpResponse(
            content=resp.content,
            status=resp.status_code,
            content_type=resp.headers.get("Content-Type", "application/json"),
        )
        return django_resp
