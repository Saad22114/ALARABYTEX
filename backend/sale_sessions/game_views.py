from django.db import transaction
from django.db.models import Count, Max, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Employee, GameChallenge, GameResult
from .notifications import notify_employee

MATH_SEASON_LENGTH = 50
MAX_MATH_LEVEL = 2_147_483_647
TTT_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))
SEEGA_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8))


def _empty_ttt_state(challenge):
    return {"board": ["", "", "", "", "", "", "", "", ""], "turn": challenge.requester_id, "winner_id": None, "draw": False}


def _record_duel_results(challenge, winner_id=None, draw=False):
    for player in (challenge.requester, challenge.opponent):
        outcome = GameResult.Outcome.DRAW if draw else GameResult.Outcome.WIN if player.pk == winner_id else GameResult.Outcome.LOSS
        GameResult.objects.create(
            employee=player,
            employee_name=player.name,
            game=challenge.game,
            outcome=outcome,
            difficulty=GameResult.Difficulty.MEDIUM,
        )


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


class GameCommunityView(APIView):
    """إعداد ظهور نقاط الفوز وترتيب الموظفين وطلبات اللعب."""

    permission_section = "@identity"

    @staticmethod
    def _challenge_data(challenge, employee):
        other = challenge.opponent if challenge.requester_id == employee.pk else challenge.requester
        game_state = challenge.game_state or (_empty_ttt_state(challenge) if challenge.game == GameResult.Game.TIC_TAC_TOE else {"choices": {}, "winner_id": None, "draw": False})
        if challenge.game == GameResult.Game.ROCK_PAPER_SCISSORS and challenge.status == GameChallenge.Status.ACCEPTED:
            choices = game_state.get("choices", {})
            all_chosen = str(challenge.requester_id) in choices and str(challenge.opponent_id) in choices
            if not all_chosen:
                own_choice = choices.get(str(employee.pk))
                game_state = {**game_state, "choices": {str(employee.pk): own_choice} if own_choice else {}}
        return {
            "id": challenge.pk,
            "requester_id": challenge.requester_id,
            "opponent_id": challenge.opponent_id,
            "game": challenge.game,
            "status": challenge.status,
            "created_at": challenge.created_at,
            "updated_at": challenge.updated_at,
            "is_incoming": challenge.opponent_id == employee.pk,
            "other_employee": {"id": other.pk, "name": other.name, "avatar": other.avatar, "avatar_image": other.avatar_image},
            "game_state": game_state,
        }

    def get(self, request):
        employee = getattr(request.user, "employee", None)
        if employee is None:
            return Response({"detail": "حساب الموظف غير مرتبط"}, status=status.HTTP_403_FORBIDDEN)

        leaderboard_scores = GameResult.objects.filter(employee__show_game_level=True).values(
            "employee_id", "employee__name", "employee__avatar", "employee__avatar_image",
        ).annotate(
            wins=Count("id", filter=Q(outcome=GameResult.Outcome.WIN)),
            math_level=Max("level", filter=Q(game=GameResult.Game.MATH_LEVELS, outcome=GameResult.Outcome.WIN)),
        ).order_by("-wins", "employee__name")[:50]
        leaderboard = list(Employee.objects.filter(show_game_level=True, is_active=True).values(
            "id", "name", "avatar", "avatar_image",
        ))
        scores = {row["employee_id"]: row for row in leaderboard_scores}
        for row in leaderboard:
            score = scores.get(row["id"], {})
            row["wins"] = score.get("wins", 0)
            row["math_level"] = score.get("math_level") or 0
        leaderboard.sort(key=lambda row: (-row["wins"], row["name"]))

        challenges = GameChallenge.objects.filter(
            Q(requester=employee) | Q(opponent=employee)
        ).select_related("requester", "opponent")[:60]
        return Response({
            "show_game_level": employee.show_game_level,
            "employees": list(Employee.objects.filter(is_active=True, user__isnull=False).exclude(pk=employee.pk).order_by("name").values("id", "name", "avatar", "avatar_image")),
            "leaderboard": leaderboard,
            "challenges": [self._challenge_data(item, employee) for item in challenges],
        })

    def patch(self, request):
        employee = getattr(request.user, "employee", None)
        value = request.data.get("show_game_level")
        if employee is None:
            return Response({"detail": "حساب الموظف غير مرتبط"}, status=status.HTTP_403_FORBIDDEN)
        if not isinstance(value, bool):
            return Response({"show_game_level": "أرسل true أو false"}, status=status.HTTP_400_BAD_REQUEST)
        Employee.objects.filter(pk=employee.pk).update(show_game_level=value)
        return Response({"show_game_level": value})

    def post(self, request):
        employee = getattr(request.user, "employee", None)
        if employee is None:
            return Response({"detail": "حساب الموظف غير مرتبط"}, status=status.HTTP_403_FORBIDDEN)
        action = request.data.get("action")
        if action == "request":
            try:
                opponent_id = int(request.data.get("opponent_id"))
            except (TypeError, ValueError):
                return Response({"opponent_id": "اختر موظفًا صالحًا"}, status=status.HTTP_400_BAD_REQUEST)
            game = request.data.get("game")
            if game not in {GameResult.Game.TIC_TAC_TOE, GameResult.Game.ROCK_PAPER_SCISSORS, GameResult.Game.SEEGA}:
                return Response({"game": "اللعبة غير متاحة للمواجهة المباشرة حاليًا"}, status=status.HTTP_400_BAD_REQUEST)
            if opponent_id == employee.pk:
                return Response({"opponent_id": "لا يمكنك تحدي نفسك"}, status=status.HTTP_400_BAD_REQUEST)
            opponent = Employee.objects.filter(pk=opponent_id, is_active=True, user__isnull=False).first()
            if opponent is None:
                return Response({"opponent_id": "الموظف غير موجود أو غير نشط"}, status=status.HTTP_404_NOT_FOUND)
            if game == GameResult.Game.TIC_TAC_TOE:
                initial_state = {"board": ["", "", "", "", "", "", "", "", ""], "turn": employee.pk, "winner_id": None, "draw": False}
            elif game == GameResult.Game.SEEGA:
                initial_state = {"board": ["O", "O", "O", "", "", "", "X", "X", "X"], "turn": employee.pk, "winner_id": None, "draw": False, "has_moved": {"X": False, "O": False}, "moves_played": 0}
            else:
                initial_state = {"choices": {}, "winner_id": None, "draw": False}
            challenge = GameChallenge.objects.create(
                requester=employee,
                opponent=opponent,
                game=game,
                game_state=initial_state,
            )
            notify_employee(
                opponent, "game_challenge", "طلب تحدٍ جديد",
                f"{employee.name} يدعوك للعب {challenge.get_game_display()}.", "/games",
            )
            return Response(self._challenge_data(challenge, employee), status=status.HTTP_201_CREATED)

        if action in {"accept", "decline"}:
            try:
                challenge_id = int(request.data.get("challenge_id"))
            except (TypeError, ValueError):
                return Response({"challenge_id": "طلب التحدي غير صالح"}, status=status.HTTP_400_BAD_REQUEST)
            with transaction.atomic():
                challenge = GameChallenge.objects.select_for_update().filter(pk=challenge_id).select_related("requester", "opponent").first()
                if challenge is None:
                    return Response({"detail": "طلب التحدي غير موجود"}, status=status.HTTP_404_NOT_FOUND)
                if challenge.opponent_id != employee.pk:
                    return Response({"detail": "يمكن للموظف المدعو فقط الرد على الطلب"}, status=status.HTTP_403_FORBIDDEN)
                if challenge.status != GameChallenge.Status.PENDING:
                    return Response({"detail": "تم الرد على هذا الطلب مسبقًا"}, status=status.HTTP_400_BAD_REQUEST)
                challenge.status = GameChallenge.Status.ACCEPTED if action == "accept" else GameChallenge.Status.DECLINED
                if action == "accept":
                    if challenge.game == GameResult.Game.TIC_TAC_TOE:
                        challenge.game_state = _empty_ttt_state(challenge)
                    elif challenge.game == GameResult.Game.SEEGA:
                        challenge.game_state = {"board": ["O", "O", "O", "", "", "", "X", "X", "X"], "turn": challenge.requester_id, "winner_id": None, "draw": False, "has_moved": {"X": False, "O": False}, "moves_played": 0}
                    else:
                        challenge.game_state = {"choices": {}, "winner_id": None, "draw": False}
                fields = ["status", "updated_at"]
                if action == "accept":
                    fields.append("game_state")
                challenge.save(update_fields=fields)
            label = "وافق على" if action == "accept" else "رفض"
            notify_employee(
                challenge.requester, "game_challenge_response", "تحديث طلب التحدي",
                f"{employee.name} {label} طلب لعب {challenge.get_game_display()}.", "/games",
            )
            return Response(self._challenge_data(challenge, employee))

        return Response({"action": "الإجراء غير صالح"}, status=status.HTTP_400_BAD_REQUEST)


class GameChallengeView(APIView):
    """حالة مباراة إكس-أو المشتركة وتسجيل حركات اللاعبين."""

    permission_section = "@identity"

    def get(self, request, challenge_id):
        employee = getattr(request.user, "employee", None)
        if employee is None:
            return Response({"detail": "حساب الموظف غير مرتبط"}, status=status.HTTP_403_FORBIDDEN)
        challenge = GameChallenge.objects.filter(pk=challenge_id).select_related("requester", "opponent").first()
        if challenge is None:
            return Response({"detail": "المباراة غير موجودة"}, status=status.HTTP_404_NOT_FOUND)
        if employee.pk not in (challenge.requester_id, challenge.opponent_id):
            return Response({"detail": "هذه المباراة ليست موجهة لحسابك"}, status=status.HTTP_403_FORBIDDEN)
        return Response(GameCommunityView._challenge_data(challenge, employee))

    def post(self, request, challenge_id):
        employee = getattr(request.user, "employee", None)
        if employee is None:
            return Response({"detail": "حساب الموظف غير مرتبط"}, status=status.HTTP_403_FORBIDDEN)
        action = request.data.get("action")
        with transaction.atomic():
            challenge = GameChallenge.objects.select_for_update().filter(pk=challenge_id).select_related("requester", "opponent").first()
            if challenge is None:
                return Response({"detail": "المباراة غير موجودة"}, status=status.HTTP_404_NOT_FOUND)
            if employee.pk not in (challenge.requester_id, challenge.opponent_id):
                return Response({"detail": "هذه المباراة ليست موجهة لحسابك"}, status=status.HTTP_403_FORBIDDEN)
            if challenge.status != GameChallenge.Status.ACCEPTED:
                return Response({"detail": "المباراة ليست نشطة"}, status=status.HTTP_400_BAD_REQUEST)
            game_state = challenge.game_state or (_empty_ttt_state(challenge) if challenge.game == GameResult.Game.TIC_TAC_TOE else {"choices": {}, "winner_id": None, "draw": False})
            if action == "forfeit":
                winner_id = challenge.opponent_id if employee.pk == challenge.requester_id else challenge.requester_id
                draw = False
                game_state.update({"winner_id": winner_id, "draw": False, "forfeit_id": employee.pk})
            elif challenge.game == GameResult.Game.TIC_TAC_TOE:
                try:
                    cell = int(request.data.get("cell"))
                except (TypeError, ValueError):
                    return Response({"cell": "اختر خانة صالحة"}, status=status.HTTP_400_BAD_REQUEST)
                if cell < 0 or cell > 8:
                    return Response({"cell": "رقم الخانة خارج اللوحة"}, status=status.HTTP_400_BAD_REQUEST)
                board = list(game_state.get("board", ["", "", "", "", "", "", "", "", ""]))
                if len(board) != 9 or game_state.get("winner_id") or game_state.get("draw"):
                    return Response({"detail": "انتهت المباراة"}, status=status.HTTP_400_BAD_REQUEST)
                if game_state.get("turn") != employee.pk:
                    return Response({"detail": "انتظر دور الموظف الآخر"}, status=status.HTTP_400_BAD_REQUEST)
                if board[cell]:
                    return Response({"detail": "هذه الخانة مشغولة"}, status=status.HTTP_400_BAD_REQUEST)

                mark = "X" if employee.pk == challenge.requester_id else "O"
                board[cell] = mark
                winner_mark = next((board[a] for a, b, c in TTT_LINES if board[a] and board[a] == board[b] == board[c]), None)
                winner_id = challenge.requester_id if winner_mark == "X" else challenge.opponent_id if winner_mark == "O" else None
                draw = winner_id is None and all(board)
                game_state = {"board": board, "turn": challenge.opponent_id if employee.pk == challenge.requester_id else challenge.requester_id, "winner_id": winner_id, "draw": draw}
            elif challenge.game == GameResult.Game.SEEGA:
                try:
                    source = int(request.data.get("from"))
                    target = int(request.data.get("to"))
                except (TypeError, ValueError):
                    return Response({"move": "اختر قطعة وخانة فارغة"}, status=status.HTTP_400_BAD_REQUEST)
                board = list(game_state.get("board", []))
                if len(board) != 9 or source < 0 or source > 8 or target < 0 or target > 8:
                    return Response({"move": "الحركة خارج اللوحة"}, status=status.HTTP_400_BAD_REQUEST)
                if game_state.get("turn") != employee.pk:
                    return Response({"detail": "انتظر دور الموظف الآخر"}, status=status.HTTP_400_BAD_REQUEST)
                mark = "X" if employee.pk == challenge.requester_id else "O"
                if board[source] != mark or board[target]:
                    return Response({"move": "اختر قطعتك ثم خانة فارغة"}, status=status.HTTP_400_BAD_REQUEST)
                board[source] = ""
                board[target] = mark
                moved = dict(game_state.get("has_moved", {"X": False, "O": False}))
                moved[mark] = True
                moves_played = int(game_state.get("moves_played", 0)) + 1
                winner_mark = next((board[a] for a, b, c in SEEGA_LINES if board[a] == mark and board[a] == board[b] == board[c]), None)
                winner_id = challenge.requester_id if winner_mark == "X" else challenge.opponent_id if winner_mark == "O" else None
                draw = winner_id is None and moves_played >= 40
                game_state = {
                    "board": board,
                    "turn": challenge.opponent_id if employee.pk == challenge.requester_id else challenge.requester_id,
                    "winner_id": winner_id,
                    "draw": draw,
                    "has_moved": moved,
                    "moves_played": moves_played,
                }
            elif challenge.game == GameResult.Game.ROCK_PAPER_SCISSORS:
                choice = request.data.get("choice")
                if choice not in {"rock", "paper", "scissors"}:
                    return Response({"choice": "اختر حجرًا أو ورقة أو مقصًا"}, status=status.HTTP_400_BAD_REQUEST)
                choices = dict(game_state.get("choices", {}))
                key = str(employee.pk)
                if key in choices:
                    return Response({"detail": "سجلت اختيارك لهذه الجولة بالفعل"}, status=status.HTTP_400_BAD_REQUEST)
                choices[key] = choice
                game_state["choices"] = choices
                winner_id = None
                draw = False
                if str(challenge.requester_id) in choices and str(challenge.opponent_id) in choices:
                    first = choices[str(challenge.requester_id)]
                    second = choices[str(challenge.opponent_id)]
                    if first == second:
                        draw = True
                    else:
                        requester_wins = (first, second) in (("rock", "scissors"), ("paper", "rock"), ("scissors", "paper"))
                        winner_id = challenge.requester_id if requester_wins else challenge.opponent_id
                game_state.update({"winner_id": winner_id, "draw": draw})
            else:
                return Response({"detail": "اللعبة غير مدعومة للمواجهة المباشرة"}, status=status.HTTP_400_BAD_REQUEST)

            challenge.game_state = game_state
            if action == "forfeit" or winner_id or draw:
                challenge.status = GameChallenge.Status.COMPLETED
                _record_duel_results(challenge, winner_id=winner_id, draw=draw)
            challenge.save(update_fields=["game_state", "status", "updated_at"])
        return Response(GameCommunityView._challenge_data(challenge, employee))
