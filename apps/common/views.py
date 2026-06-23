from rest_framework.response import Response


class EnvelopeMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if (
            isinstance(response, Response)
            and 200 <= response.status_code < 300
            and response.status_code != 204
            and isinstance(response.data, (dict, list))
            and "data" not in response.data
        ):
            response.data = {"data": response.data}
        return response
