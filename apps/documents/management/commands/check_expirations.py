from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.documents.models import Document
from apps.notifications.models import Notification

class Command(BaseCommand):
    help = 'Checks for expired documents and updates their status.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # Find approved documents that have expired
        expired_docs = Document.objects.filter(
            status=Document.STATUS_APPROVED,
            expiry_date__lt=today
        )
        
        count = expired_docs.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No expired documents found.'))
            return
            
        for doc in expired_docs:
            doc.status = Document.STATUS_EXPIRED
            doc.save(update_fields=['status'])
            
            # Notify vendor
            if doc.vendor and doc.vendor.user:
                Notification.objects.create(
                    recipient=doc.vendor.user,
                    notification_type=Notification.TYPE_WARNING,
                    title="Document Expired",
                    message=f"Your document '{doc.title}' has expired. Please submit a new one.",
                    link="/vendor/documents"
                )
                
        self.stdout.write(self.style.SUCCESS(f'Successfully updated {count} expired documents.'))
