from django.core.management.base import BaseCommand
from apps.ingestion.scraper import download_and_ingest

class Command(BaseCommand):
    help = 'Scrape DA CALABARZON website for new price monitoring PDFs and ingest them.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true', default=False,
            help='Force download and reprocess even if documents exist in the DB.',
        )
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Run the scraper but do not download files or write to DB.',
        )
        parser.add_argument(
            '--start-date', type=str, default=None,
            help='Only process documents from this date onwards (YYYY-MM-DD).',
        )

    def handle(self, *args, **options):
        force = options['force']
        dry_run = options['dry_run']
        start_date_str = options['start_date']
        
        start_date = None
        if start_date_str:
            from datetime import datetime
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(self.style.ERROR("Invalid date format. Use YYYY-MM-DD."))
                return

        self.stdout.write(self.style.MIGRATE_HEADING("Starting DA Web Scraper..."))
        
        try:
            download_and_ingest(dry_run=dry_run, force=force, start_date=start_date)
            self.stdout.write(self.style.SUCCESS("\nScraper command completed successfully."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"\nScraper encountered a critical error: {e}"))
