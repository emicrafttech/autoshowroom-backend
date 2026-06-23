from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.views import EnvelopeMixin

from .catalog import CATALOG_SOURCE, get_makes, get_models, normalize_make


class CatalogMakesView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"makes": get_makes(), "source": CATALOG_SOURCE})


class CatalogModelsView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        make = request.query_params.get("make", "").strip()
        year = request.query_params.get("year")
        year_value = int(year) if year and year.isdigit() else None
        normalized_make = normalize_make(make)
        return Response(
            {
                "make": normalized_make,
                "year": year_value,
                "models": get_models(normalized_make),
                "source": CATALOG_SOURCE,
            }
        )
