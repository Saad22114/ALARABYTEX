from django.db.models import Count, Max, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GameResult

MATH_SEASON_LENGTH = 50
MAX_MATH_LEVEL = 2_147_483_647


class GameResultsView(APIView):
    """كل موظف يسجل ويراجع نتائجه بنفسه؛ لا تُقبل هوية الموظف من العميل."""

    permission_section = "@identity"

    def get(self, request):
        employee = getattr(request.user, "employee", None)
        if employee is None:
            return Response({"detail": "حساب الموظف غير مرتبط"}, status=status.HTTP_403_FORBIDDEN)

        own_results = GameResult.objects.filter(employee=employee)
        totals = own_results.aggregate(
            wins=Count("id", filter=Q(outcome=GameResult.Outcome.WIN)),
            losses=Count("id", filter=Q(outcome=GameResult.Outcome.LOSS)),
            draws=Count("id", filter=Q(outcome=GameResult.Outcome.DRAW)),
        )
        highest_math_level = own_results.filter(
            game=GameResult.Game.MATH_LEVELS,
            outcome=GameResult.Outcome.WIN,
        ).aggregate(highest=Max("level"))["highest"] or 0
        recent = list(
            own_results.values("id", "game", "outcome", "difficulty", "level", "created_at")[:40]
        )
        return Response({
            "totals": totals,
            "results": recent,
            "math_progress": {
                "highest_level": highest_math_level,
                "unlocked_level": highest_math_level + 1,
                "season_length": MATH_SEASON_LENGTH,
            },
        })

    def post(self, request):
        employee = getattr(request.user, "employee", None)
        if employee is None:
            return Response({"detail": "حساب الموظف غير مرتبط"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data if isinstance(request.data, dict) else {}
        choices = {
            "game": {value for value, _ in GameResult.Game.choices},
            "outcome": {value for value, _ in GameResult.Outcome.choices},
            "difficulty": {value for value, _ in GameResult.Difficulty.choices},
        }
        errors = {
            field: "قيمة غير صالحة"
            for field, valid_values in choices.items()
            if data.get(field) not in valid_values
        }
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        level = 0
        if data["game"] == GameResult.Game.MATH_LEVELS:
            try:
                level = int(data.get("level", 0))
            except (TypeError, ValueError):
                level = 0
            if level < 1 or level > MAX_MATH_LEVEL:
                return Response({"level": f"المستوى يجب أن يكون بين 1 و{MAX_MATH_LEVEL}"}, status=status.HTTP_400_BAD_REQUEST)
            highest_completed = GameResult.objects.filter(
                employee=employee,
                game=GameResult.Game.MATH_LEVELS,
                outcome=GameResult.Outcome.WIN,
            ).aggregate(highest=Max("level"))["highest"] or 0
            if level > highest_completed + 1:
                return Response({"level": "يجب اجتياز المستوى السابق أولًا"}, status=status.HTTP_400_BAD_REQUEST)

        result = GameResult.objects.create(
            employee=employee,
            employee_name=employee.name,
            game=data["game"],
            outcome=data["outcome"],
            difficulty=data["difficulty"],
            level=level,
        )
        return Response(
            {
                "id": result.id,
                "game": result.game,
                "outcome": result.outcome,
                "difficulty": result.difficulty,
                "level": result.level,
                "created_at": result.created_at,
            },
            status=status.HTTP_201_CREATED,
        )
