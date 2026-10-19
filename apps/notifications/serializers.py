from rest_framework import serializers
from urllib.parse import unquote, urlsplit
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'notification_type', 'notification_type_display',
                  'title', 'message', 'link', 'is_read', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_link(self, value):
        """Notification targets must remain on this application origin."""
        if not value:
            return value

        decoded = unquote(value).strip()
        parsed = urlsplit(decoded)
        if (
            not decoded.startswith('/')
            or decoded.startswith('//')
            or parsed.scheme
            or parsed.netloc
            or '\\' in decoded
            or any(ord(character) < 32 for character in decoded)
        ):
            raise serializers.ValidationError('Link must be a safe internal application route.')
        return value
