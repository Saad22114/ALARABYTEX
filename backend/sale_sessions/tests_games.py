from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from sale_sessions.models import Employee, GameChallenge, GameResult, Notification


class GameCommunityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user("game_a", password="pass1234")
        cls.other_user = User.objects.create_user("game_b", password="pass1234")
        cls.hidden_user = User.objects.create_user("game_c", password="pass1234")
        cls.employee = Employee.objects.create(user=cls.user, name="موظف أ", show_game_level=True)
        cls.other = Employee.objects.create(user=cls.other_user, name="موظف ب")
        cls.hidden = Employee.objects.create(user=cls.hidden_user, name="موظف ج")

    def test_level_visibility_is_opt_in_and_private(self):
        GameResult.objects.create(employee=self.employee, employee_name=self.employee.name, game="tic_tac_toe", outcome="win", difficulty="easy")
        GameResult.objects.create(employee=self.hidden, employee_name=self.hidden.name, game="tic_tac_toe", outcome="win", difficulty="easy")
        client = APIClient()
        client.force_authenticate(self.other_user)

        data = client.get("/api/games/community/").data
        self.assertEqual([row["id"] for row in data["leaderboard"]], [self.employee.pk])
        self.assertEqual(data["leaderboard"][0]["wins"], 1)

        changed = client.patch("/api/games/community/", {"show_game_level": True}, format="json")
        self.assertEqual(changed.status_code, 200)
        self.assertTrue(Employee.objects.get(pk=self.other.pk).show_game_level)

    def test_request_and_only_invited_employee_can_answer(self):
        sender = APIClient()
        sender.force_authenticate(self.user)
        recipient = APIClient()
        recipient.force_authenticate(self.other_user)

        created = sender.post("/api/games/community/", {
            "action": "request", "opponent_id": self.other.pk, "game": "tic_tac_toe",
        }, format="json")
        self.assertEqual(created.status_code, 201)
        challenge = GameChallenge.objects.get(pk=created.data["id"])
        self.assertEqual(challenge.status, GameChallenge.Status.PENDING)
        self.assertTrue(Notification.objects.filter(recipient=self.other, kind="game_challenge").exists())

        forbidden = sender.post("/api/games/community/", {
            "action": "accept", "challenge_id": challenge.pk,
        }, format="json")
        self.assertEqual(forbidden.status_code, 403)

        accepted = recipient.post("/api/games/community/", {
            "action": "accept", "challenge_id": challenge.pk,
        }, format="json")
        self.assertEqual(accepted.status_code, 200)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, GameChallenge.Status.ACCEPTED)

        for client, cell in ((sender, 0), (recipient, 3), (sender, 1), (recipient, 4), (sender, 2)):
            moved = client.post(f"/api/games/challenges/{challenge.pk}/", {"cell": cell}, format="json")
            self.assertEqual(moved.status_code, 200, moved.data)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, GameChallenge.Status.COMPLETED)
        self.assertEqual(challenge.game_state["winner_id"], self.employee.pk)
        self.assertEqual(GameResult.objects.filter(game="tic_tac_toe").count(), 2)

    def test_rps_choices_stay_hidden_until_both_players_choose(self):
        sender = APIClient()
        sender.force_authenticate(self.user)
        recipient = APIClient()
        recipient.force_authenticate(self.other_user)
        created = sender.post("/api/games/community/", {
            "action": "request", "opponent_id": self.other.pk, "game": "rock_paper_scissors",
        }, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["game"], "rock_paper_scissors")
        challenge_id = created.data["id"]
        accepted = recipient.post("/api/games/community/", {"action": "accept", "challenge_id": challenge_id}, format="json")
        self.assertEqual(accepted.data["game"], "rock_paper_scissors")

        first_choice = sender.post(f"/api/games/challenges/{challenge_id}/", {"choice": "rock"}, format="json")
        self.assertEqual(first_choice.status_code, 200)
        self.assertEqual(first_choice.data["game_state"]["choices"], {str(self.employee.pk): "rock"})
        hidden_choice = recipient.get(f"/api/games/challenges/{challenge_id}/")
        self.assertEqual(hidden_choice.data["game_state"]["choices"], {})

        second_choice = recipient.post(f"/api/games/challenges/{challenge_id}/", {"choice": "scissors"}, format="json")
        self.assertEqual(second_choice.status_code, 200)
        self.assertEqual(second_choice.data["status"], GameChallenge.Status.COMPLETED)
        self.assertEqual(second_choice.data["game_state"]["winner_id"], self.employee.pk)
        outcomes = dict(GameResult.objects.filter(game="rock_paper_scissors").values_list("employee_id", "outcome"))
        self.assertEqual(outcomes[self.employee.pk], GameResult.Outcome.WIN)
        self.assertEqual(outcomes[self.other.pk], GameResult.Outcome.LOSS)

    def test_seega_live_match_uses_only_horizontal_or_vertical_win(self):
        sender = APIClient()
        sender.force_authenticate(self.user)
        recipient = APIClient()
        recipient.force_authenticate(self.other_user)
        created = sender.post("/api/games/community/", {
            "action": "request", "opponent_id": self.other.pk, "game": "seega",
        }, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["game"], "seega")
        challenge_id = created.data["id"]
        recipient.post("/api/games/community/", {"action": "accept", "challenge_id": challenge_id}, format="json")

        sequence = ((sender, 6, 3), (recipient, 0, 6), (sender, 7, 4), (recipient, 1, 0), (sender, 8, 5))
        for client, source, target in sequence:
            moved = client.post(f"/api/games/challenges/{challenge_id}/", {"from": source, "to": target}, format="json")
            self.assertEqual(moved.status_code, 200, moved.data)
        self.assertEqual(moved.data["status"], GameChallenge.Status.COMPLETED)
        self.assertEqual(moved.data["game_state"]["winner_id"], self.employee.pk)
        self.assertEqual(moved.data["game_state"]["board"][3:6], ["X", "X", "X"])

    def test_forfeit_records_loser_and_opponent_win(self):
        sender = APIClient()
        sender.force_authenticate(self.user)
        recipient = APIClient()
        recipient.force_authenticate(self.other_user)
        created = sender.post("/api/games/community/", {
            "action": "request", "opponent_id": self.other.pk, "game": "tic_tac_toe",
        }, format="json")
        challenge_id = created.data["id"]
        recipient.post("/api/games/community/", {"action": "accept", "challenge_id": challenge_id}, format="json")

        resigned = recipient.post(f"/api/games/challenges/{challenge_id}/", {"action": "forfeit"}, format="json")
        self.assertEqual(resigned.status_code, 200)
        self.assertEqual(resigned.data["status"], GameChallenge.Status.COMPLETED)
        self.assertEqual(resigned.data["game_state"]["forfeit_id"], self.other.pk)
        outcomes = dict(GameResult.objects.filter(game="tic_tac_toe").values_list("employee_id", "outcome"))
        self.assertEqual(outcomes[self.employee.pk], GameResult.Outcome.WIN)
        self.assertEqual(outcomes[self.other.pk], GameResult.Outcome.LOSS)
