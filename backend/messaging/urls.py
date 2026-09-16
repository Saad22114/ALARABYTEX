from django.urls import path

from .views import (
    ConversationListView,
    DeleteMessageView,
    EditMessageView,
    MessageThreadView,
    SendMessageView,
    UnreadCountView,
)

app_name = "messaging"

urlpatterns = [
    path("messaging/conversations/", ConversationListView.as_view(), name="conversations"),
    path("messaging/messages/", MessageThreadView.as_view(), name="thread"),
    path("messaging/send/", SendMessageView.as_view(), name="send"),
    path("messaging/messages/<int:pk>/edit/", EditMessageView.as_view(), name="edit"),
    path("messaging/messages/<int:pk>/delete/", DeleteMessageView.as_view(), name="delete"),
    path("messaging/unread/", UnreadCountView.as_view(), name="unread"),
]