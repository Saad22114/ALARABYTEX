from rest_framework import serializers

from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.name", read_only=True)
    receiver_name = serializers.CharField(source="receiver.name", read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)
    reply_to_id = serializers.IntegerField(read_only=True)
    reply_from_name = serializers.CharField(source="reply_to.sender.name", read_only=True, default="")

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "sender_name",
            "receiver",
            "receiver_name",
            "body",
            "read_at",
            "edited_at",
            "deleted_at",
            "is_deleted",
            "reply_to_id",
            "reply_to_body",
            "reply_from_name",
            "created_at",
        ]

    def validate(self, attrs):
        if attrs["sender"] == attrs["receiver"]:
            raise serializers.ValidationError(
                {"receiver": "لا يمكنك إرسال رسالة لنفسك"}
            )
        return attrs