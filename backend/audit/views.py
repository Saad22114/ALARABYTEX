from django.db.models import Q
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog


class AuditLogPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


class AuditLogView(APIView):
    permission_section = "settings"

    def get(self, request):
        qs = AuditLog.objects.select_related("employee").all()
        params = request.query_params

        employee = params.get("employee")
        if employee:
            qs = qs.filter(employee_id=employee)
        section = params.get("section")
        if section:
            qs = qs.filter(section=section)
        action = params.get("action")
        if action:
            qs = qs.filter(action=action)
        model = params.get("model")
        if model:
            qs = qs.filter(model_name__icontains=model)
        date_from = params.get("from")
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        date_to = params.get("to")
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)
        q = params.get("q")
        if q:
            qs = qs.filter(
                Q(object_repr__icontains=q)
                | Q(model_name__icontains=q)
                | Q(employee__name__icontains=q)
            )

        paginator = AuditLogPagination()
        page = paginator.paginate_queryset(qs, request)
        data = [
            {
                "id": a.id,
                "timestamp": a.timestamp,
                "employee_id": a.employee_id,
                "employee_name": a.employee.name if a.employee else None,
                "section": a.section,
                "action": a.action,
                "action_label": a.get_action_display(),
                "model_name": a.model_name,
                "object_id": a.object_id,
                "object_repr": a.object_repr,
                "changes": a.changes,
                "ip": a.ip,
                "method": a.method,
                "path": a.path,
            }
            for a in page
        ]
        return Response(
            {
                "count": paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": data,
            },
            status=status.HTTP_200_OK,
        )