from .models import SiteSettings


def site(request):
    return {"cafe": SiteSettings.load()}
