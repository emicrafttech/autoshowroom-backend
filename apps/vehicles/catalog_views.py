from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.views import EnvelopeMixin

from .catalog import (
    CATALOG_SOURCE,
    get_full_catalog,
    get_makes,
    get_models,
    get_trims,
    normalize_make,
    normalize_model,
)


class CatalogTreeView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(get_full_catalog())


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


class CatalogTrimsView(EnvelopeMixin, APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        make = request.query_params.get("make", "").strip()
        model = request.query_params.get("model", "").strip()
        normalized_make = normalize_make(make)
        normalized_model = normalize_model(normalized_make, model)
        return Response(
            {
                "make": normalized_make,
                "model": normalized_model,
                "trims": get_trims(normalized_make, normalized_model),
                "source": CATALOG_SOURCE,
            }
        )
