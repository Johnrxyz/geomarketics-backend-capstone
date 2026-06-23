import os
import requests
import datetime
import urllib.parse
from bs4 import BeautifulSoup
from django.conf import settings
from apps.ingestion.models import SourceDocument
from apps.ingestion.pipeline.orchestrator import run_pipeline
from apps.ingestion.management.commands.ingest_pdf import _infer_date

# Adjust if DA changes their URL structure
DEFAULT_TARGET_URL = os.environ.get(
    'DA_BANTAY_PRESYO_URL', 
    'https://calabarzon.da.gov.ph/da-calabarzon-bantay-presyo/'
)

def download_and_ingest(dry_run: bool = False, force: bool = False, start_date: datetime.date = None):
    """
    Scrapes the DA CALABARZON website for price monitoring PDFs,
    downloads new ones, and passes them to the ingestion pipeline.
    """
    print(f"Fetching target URL: {DEFAULT_TARGET_URL}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(DEFAULT_TARGET_URL, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to fetch {DEFAULT_TARGET_URL}: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    links = soup.find_all('a')
    
    pdf_links = []
    for link in links:
        href = link.get('href')
        if not href:
            continue
            
        if 'drive.google.com/file/d/' in href:
            # Extract file ID from https://drive.google.com/file/d/{FILE_ID}/view
            parts = href.split('/d/')
            if len(parts) > 1:
                file_id = parts[1].split('/')[0]
                # Construct direct download URL
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                
                # Use the link text as the filename (e.g. "June 1, 2026")
                link_text = link.text.strip().replace('/', '-').replace('\\', '-')
                if not link_text:
                    link_text = f"DA_Report_{file_id}"
                
                if not link_text.lower().endswith('.pdf'):
                    filename = f"{link_text}.pdf"
                else:
                    filename = link_text
                    
                pdf_links.append((download_url, filename))

    # De-duplicate links by URL
    unique_links = {}
    for url, filename in pdf_links:
        unique_links[url] = filename
    
    print(f"Found {len(unique_links)} Google Drive PDF links on the page.")

    # Create local storage directory
    media_root = getattr(settings, 'MEDIA_ROOT', '/tmp')
    if not media_root or media_root == '':
        media_root = '/tmp'
        
    download_dir = os.path.join(media_root, 'da_price_reports')
    os.makedirs(download_dir, exist_ok=True)

    processed_count = 0
    skipped_count = 0
    failed_count = 0

    for url, filename in unique_links.items():
        print(f"\nProcessing: {filename}")
        
        # Check if already processed to avoid downloading repeatedly
        if not force and SourceDocument.objects.filter(source_filename=filename).exists():
            print("  [SKIPPED] Document already exists in database.")
            skipped_count += 1
            continue

        # Infer publication date
        pub_date = _infer_date(filename)
        if not pub_date:
            print("  [SKIPPED] Could not infer date from filename. (Not a valid Bantay Presyo file?)")
            skipped_count += 1
            continue
            
        if start_date and pub_date < start_date:
            print(f"  [SKIPPED] Document date {pub_date} is before start_date {start_date}.")
            skipped_count += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] Would download {url} to {download_dir} and ingest for date {pub_date}.")
            processed_count += 1
            continue

        # Download the file
        local_path = os.path.join(download_dir, filename)
        try:
            print(f"  Downloading from {url}...")
            r = requests.get(url, headers=headers, stream=True, timeout=30)
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        except requests.RequestException as e:
            print(f"  [FAILED] Download error: {e}")
            failed_count += 1
            continue

        # Hand off to pipeline
        try:
            doc = run_pipeline(
                file_path=local_path,
                publication_date=pub_date,
                source_filename=filename,
                source_url=url,
                source_type=SourceDocument.SOURCE_DA_WEBSITE,
                force_reprocess=force,
            )
            print(f"  [INGESTED] Pipeline returned status: {doc.status} (pk={doc.pk})")
            if doc.status == 'PROCESSED':
                processed_count += 1
            else:
                skipped_count += 1
        except Exception as e:
            print(f"  [FAILED] Pipeline unhandled error: {e}")
            failed_count += 1
            
    print(f"\nScraping complete. Processed/Ingested: {processed_count}, Skipped: {skipped_count}, Failed: {failed_count}")
