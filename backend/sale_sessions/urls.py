from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import EmployeeViewSet, PermissionTemplateViewSet, SaleSessionViewSet, SectionsView
from .game_views import GameChallengeView, GameCommunityView, GameResultsView

router = DefaultRouter()
router.register("employees", EmployeeViewSet, basename="employee")
router.register("permission-templates", PermissionTemplateViewSet, basename="permission-template")
router.register("sale-sessions", SaleSessionViewSet, basename="sale-session")

urlpatterns = [
    path("sections/", SectionsView.as_view(), name="sections"),
    path("games/results/", GameResultsView.as_view(), name="game-results"),
    path("games/community/", GameCommunityView.as_view(), name="game-community"),
    path("games/challenges/<int:challenge_id>/", GameChallengeView.as_view(), name="game-challenge"),
] + router.urls
