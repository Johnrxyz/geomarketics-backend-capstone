"""
Management command: ingest_pdf

Usage:
  # Single file
  python manage.py ingest_pdf "path/to/May 18, 2026.pdf"

  # Entire directory (all *.pdf files)
  python manage.py ingest_pdf --dir "D:/...bantay_presyo_audit/format_B"

  # Force reprocess already-ingested documents
  python manage.py ingest_pdf --dir "..." --force

  # Dry run (extract + normalize + detect format, no DB writes)
  python manage.py ingest_pdf "..." --dry-run

Options:
  --dir PATH        Process all PDF files in a directory
  --force           Re-run pipeline even if document already exists
  --dry-run         Print results without writing to DB
  --date DATE       Override publication date (YYYY-MM-DD); auto-detected from
                    filename by default
"""

from __future__ import annotations

import datetime
import glob
import os
import re
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.ingestion.pipeline.orchestrator import run_pipeline
from apps.ingestion.pipeline.extractor import extract
from apps.ingestion.pipeline.normalizer import normalize
from apps.ingestion.pipeline.format_detector import detect_format
from apps.ingestion.pipeline.exceptions import ExtractionError, ImageOnlyPDFError


# Filename patterns for auto-detecting the publication date
_DATE_PATTERNS = [
    # "May 18, 2026.pdf"  /  "June 1, 2026.pdf"
    (r'(?P<month>\w+)\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{4})', '%B %d %Y'),
    # "2026-05-18.pdf"
    (r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})', '%Y-%m-%d'),
]

_MONTH_TYPOS: dict[str, str] = {
    # Known typo in corpus: "May 22, 206.pdf"
    '206': '2026',
}


def _infer_date(filename: str) -> datetime.date | None:
    """Try to extract a publication date from the PDF filename."""
    stem = os.path.splitext(os.path.basename(filename))[0]

    # Fix known typos in year portion before parsing
    for wrong, right in _MONTH_TYPOS.items():
        stem = stem.replace(wrong, right)

    for pattern, fmt in _DATE_PATTERNS:
        m = re.search(pattern, stem, re.IGNORECASE)
        if m:
            try:
                groups = m.groupdict()
                date_str = f"{groups['month']} {int(groups['day']):02d} {groups['year']}"
                return datetime.datetime.strptime(date_str, fmt).date()
            except (ValueError, KeyError):
                continue

    return None


class Command(BaseCommand):
    help = 'Ingest one or more DA CALABARZON price PDFs into SourceDocument records.'

    def add_arguments(self, parser):
        parser.add_argument(
            'files', nargs='*', type=str,
            help='Path(s) to PDF file(s) to ingest.',
        )
        parser.add_argument(
            '--dir', type=str, default=None,
            help='Process all *.pdf files in this directory.',
        )
        parser.add_argument(
            '--force', action='store_true', default=False,
            help='Re-run the pipeline even if the document already exists.',
        )
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Run extraction/normalization/detection but do not write to DB.',
        )
        parser.add_argument(
            '--date', type=str, default=None,
            help='Override publication date (YYYY-MM-DD). Applies to all files.',
        )

    def handle(self, *args, **options):
        files: list[str] = list(options['files'])

        # Collect files from --dir
        if options['dir']:
            pattern = os.path.join(options['dir'], '*.pdf')
            dir_files = sorted(glob.glob(pattern))
            if not dir_files:
                raise CommandError(f"No PDF files found in: {options['dir']}")
            files.extend(dir_files)

        if not files:
            raise CommandError('Provide at least one PDF file or use --dir.')

        # Override date
        override_date: datetime.date | None = None
        if options['date']:
            try:
                override_date = datetime.date.fromisoformat(options['date'])
            except ValueError:
                raise CommandError(f"Invalid --date value: {options['date']} (expected YYYY-MM-DD)")

        dry_run    = options['dry_run']
        force      = options['force']
        total      = len(files)
        results    = {'processed': 0, 'skipped': 0, 'failed': 0}

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nIngesting {total} PDF file(s) — dry_run={dry_run}, force={force}\n"
        ))

        for file_path in files:
            file_path = os.path.abspath(file_path)
            filename  = os.path.basename(file_path)

            if not os.path.isfile(file_path):
                self.stderr.write(self.style.ERROR(f"  ✗ NOT FOUND: {filename}"))
                results['failed'] += 1
                continue

            pub_date = override_date or _infer_date(filename)
            if pub_date is None:
                self.stderr.write(self.style.WARNING(
                    f"  ⚠ Cannot infer date from filename: {filename}. "
                    "Skipping. Use --date to override."
                ))
                results['skipped'] += 1
                continue

            self.stdout.write(f"  > {filename}  ({pub_date.isoformat()})", ending='')

            if dry_run:
                self._dry_run_file(file_path, filename)
                results['processed'] += 1
                continue

            try:
                doc = run_pipeline(
                    file_path=file_path,
                    publication_date=pub_date,
                    source_filename=filename,
                    force_reprocess=force,
                )
                status_display = {
                    'PROCESSED': self.style.SUCCESS,
                    'SKIPPED_UNSUPPORTED_FORMAT': self.style.WARNING,
                    'UNSUPPORTED_IMAGE_PDF': self.style.WARNING,
                    'FAILED': self.style.ERROR,
                }.get(doc.status, str)

                self.stdout.write(f"  [{status_display(doc.status)}]  pk={doc.pk}")

                if doc.status == 'PROCESSED':
                    results['processed'] += 1
                elif doc.status in ('SKIPPED_UNSUPPORTED_FORMAT', 'UNSUPPORTED_IMAGE_PDF'):
                    results['skipped'] += 1
                else:
                    results['failed'] += 1

            except Exception as exc:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f"\n  ✗ UNHANDLED: {exc}"))
                results['failed'] += 1

        # ── Summary ──────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nDone. Processed: {results['processed']}  "
            f"Skipped: {results['skipped']}  "
            f"Failed: {results['failed']}\n"
        ))

        if results['failed']:
            sys.exit(1)

    def _dry_run_file(self, file_path: str, filename: str) -> None:
        """Run extraction and format detection without touching the DB."""
        try:
            extraction = extract(file_path)
            norm       = normalize(extraction)
            fmt        = detect_format(norm)
            self.stdout.write(
                f"  [DRY-RUN]  pages={extraction.page_count}"
                f"  text_pages={extraction.text_page_count}"
                f"  format={fmt.value}"
            )
        except ImageOnlyPDFError:
            self.stdout.write(self.style.WARNING(f"  [DRY-RUN]  UNSUPPORTED_IMAGE_PDF"))
        except ExtractionError as exc:
            self.stdout.write(self.style.ERROR(f"  [DRY-RUN]  EXTRACTION_ERROR: {exc}"))
