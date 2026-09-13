from rest_framework import viewsets, status
from rest_framework.response import Response
from django.conf import settings
from .models import Branch
from .serializers import BranchSerializer


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    search_fields = ["name", "code", "city", "phone"]
    ordering_fields = ["name", "code", "created_at"]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.daily_sales.exists() or instance.expenses.exists():
            return Response(
                {"detail": settings.API_MESSAGES["branch_in_use"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response(
            {"detail": settings.API_MESSAGES["deleted"]},
            status=status.HTTP_200_OK,
        )
