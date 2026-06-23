from rest_framework import status
from rest_framework.response import Response


def success_response(data=None, status_code=status.HTTP_200_OK) -> Response:
    return Response({"data": data}, status=status_code)
