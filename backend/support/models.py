from django.db import models
from django.conf import settings


class SupportTicket(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    ticket_id = models.CharField(max_length=30, unique=True)
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=100, default='Order Issue')
    priority = models.CharField(max_length=20, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='medium')
    status = models.CharField(max_length=20, choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('resolved', 'Resolved'), ('cancelled', 'Cancelled')], default='open')
    message = models.TextField()
    admin_reply = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ticket_id} - {self.subject} ({self.status})"
