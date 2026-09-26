from rest_framework.response import Response
from rest_framework.views import APIView

from .alerts import alerts_summary, build_alerts


class AlertsCenterView(APIView):
    """مركز التنبيهات الذكية: قائمة موحّدة مرتّبة بالخطورة.

    لكل تنبيه حقل ``section`` يُستخدم لتخطّي ما لا يملك المستخدم صلاحية
    رؤيته، فيرى كل موظف ما يخصّفرعـه وصلاحياته فقط.
    """

    permission_section = "dashboard"

    def get(self, request):
        alerts = build_alerts(request)
        return Response(
            {
                "summary": alerts_summary(alerts),
                "alerts": alerts,
            }
        )
