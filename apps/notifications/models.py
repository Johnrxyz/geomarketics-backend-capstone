from django.db import models
from django.conf import settings


class Notification(models.Model):
    TYPE_INFO = 'info'
    TYPE_WARNING = 'warning'
    TYPE_ERROR = 'error'
    TYPE_SUCCESS = 'success'
    TYPE_CHOICES = [
        (TYPE_INFO, 'Info'),
        (TYPE_WARNING, 'Warning'),
        (TYPE_ERROR, 'Error'),
        (TYPE_SUCCESS, 'Success'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_INFO)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title} -> {self.recipient}"
