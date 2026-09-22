from django.urls import path

from .views import (
    ConversationListView,
    DeleteMessageView,
    EditMessageView,
    EmployeeContactListView,
    ForwardMessageView,
    MessageSearchView,
    MessageThreadView,
    SendMessageView,
    UnreadCountView,
)

app_name = "messaging"

urlpatterns = [
    path("messaging/conversations/", ConversationListView.as_view(), name="conversations"),
    path("messaging/contacts/", EmployeeContactListView.as_view(), name="contacts"),
    path("messaging/search/", MessageSearchView.as_view(), name="search"),
    path("messaging/forward/", ForwardMessageView.as_view(), name="forward"),
    path("messaging/messages/", MessageThreadView.as_view(), name="thread"),
    path("messaging/send/", SendMessageView.as_view(), name="send"),
    path("messaging/messages/<int:pk>/edit/", EditMessageView.as_view(), name="edit"),
    path("messaging/messages/<int:pk>/delete/", DeleteMessageView.as_view(), name="delete"),
    path("messaging/unread/", UnreadCountView.as_view(), name="unread"),
]