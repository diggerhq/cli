from rest_framework import permissions

from drf_yasg.views import get_schema_view
from drf_yasg import openapi


# Schema configuration
schema_view = get_schema_view(
    openapi.Info(
        title="cookiecutter-drf",
        default_version="0.1.0",
    ),
    validators=["flex", "ssv"],
    public=False,
    permission_classes=(permissions.AllowAny,),
)
