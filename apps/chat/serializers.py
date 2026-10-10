from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)
    message = serializers.CharField(max_length=4000)
    display_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
