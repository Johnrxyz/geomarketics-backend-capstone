from django.conf import settings
from apps.documents.models import Document, DocumentPage, ComplianceSignal
from apps.documents.services.ocr import extract_text_paddleocr
from apps.documents.services.extraction import DocumentExtractionService

def process_uploaded_document(document_id):
    """
    Orchestrates the multi-page OCR, page classification, and data extraction.
    Handles PROCESSING -> PENDING status transition.

    Important: Once submit-contract is called and the document is in PROCESSING,
    we must always complete (transition to PENDING) — never revert to INCOMPLETE.
    Page-detection warnings are stored for admin info but do NOT block the workflow.
    """
    try:
        document = Document.objects.get(id=document_id)
        
        # Mark OCR status as active
        document.ocr_status = 'processing'
        document.save(update_fields=['ocr_status'])
        
        pages = document.pages.all().order_by('page_upload_order')
        
        if not pages.exists() and not document.file:
            document.ocr_status = 'failed'
            document.status = Document.STATUS_PENDING  # Still send to admin review
            document.save(update_fields=['ocr_status', 'status'])
            return

        is_contract = document.document_type == Document.TYPE_CONTRACT

        # 1. Process pages via OCR Provider
        provider = DocumentExtractionService.get_provider()
        
        page_paths = []
        pages_to_process = []
        for page in pages:
            if not page.raw_ocr_text and page.file:
                page_paths.append(page.file.path)
                pages_to_process.append(page)
                
        if page_paths:
            provider_results = provider.process_document(page_paths, document.document_type)
            
            for i, page in enumerate(pages_to_process):
                res = provider_results[i]
                raw_text = res.get("raw_text", "")
                page.raw_ocr_text = raw_text
                
                if is_contract:
                    detected_page = res.get("page_number")
                    confidence = res.get("confidence", 0.0)
                    if detected_page is None:
                        ComplianceSignal.objects.get_or_create(
                            vendor=document.vendor,
                            document=document,
                            signal_type='invalid_contract_page',
                            defaults={
                                'description': f"Page {page.page_upload_order}: Could not confidently identify page type. Admin should verify manually.",
                                'source': 'OCR'
                            }
                        )
                    page.detected_page_number = detected_page
                    page.page_detection_confidence = confidence
                else:
                    page.detected_page_number = 1
                    page.page_detection_confidence = 1.0
                
                # Merge extracted data into document if present
                extracted = res.get("extracted_data")
                if extracted:
                    if document.extracted_data is None:
                        document.extracted_data = {}
                    document.extracted_data.update({k: v for k, v in extracted.items() if v})
                
                page.save(update_fields=['raw_ocr_text', 'detected_page_number', 'page_detection_confidence'])

        # 2. Combine text — use detected order for contracts, upload order as fallback
        if is_contract:
            # Prefer detected ordering but fall back to upload order if detection failed
            detected_ordered = list(
                document.pages.filter(detected_page_number__isnull=False).order_by('detected_page_number')
            )
            undetected = list(
                document.pages.filter(detected_page_number__isnull=True).order_by('page_upload_order')
            )
            ordered_pages = detected_ordered + undetected
        else:
            ordered_pages = list(pages)
            
        combined_text = "\n\n".join([p.raw_ocr_text for p in ordered_pages if p.raw_ocr_text])
        document.raw_ocr_text = combined_text

        # 3. Build classification metadata for admin auditability
        detected_pages = [p.detected_page_number for p in pages if p.detected_page_number is not None]
        unique_pages = set(detected_pages)
        unidentified_count = pages.filter(detected_page_number__isnull=True).count()

        validation_notes = []
        auto_resubmit = False
        resubmit_reason = ""
        
        if is_contract:
            missing = [p for p in [1, 2, 3] if p not in unique_pages]
            duplicates_detected = len(detected_pages) != len(unique_pages)
            
            if missing or duplicates_detected:
                auto_resubmit = True
                if duplicates_detected:
                    resubmit_reason = "Duplicate pages detected. Please ensure you upload exactly Page 1, Page 2, and Page 3."
                    validation_notes.append("❌ Auto-rejected due to duplicate pages.")
                elif missing:
                    resubmit_reason = f"Missing required pages. Please ensure all 3 pages are uploaded correctly."
                    validation_notes.append("❌ Auto-rejected due to missing/unidentifiable pages.")
                
                # Also log warning
                validation_notes.append(f"Pages successfully identified: {list(unique_pages)}")

        # 4. Extract structured data
        # If the provider is Paddle, it returns empty extracted_data, so we fallback to regex
        # If Gemini, it already populated document.extracted_data above.
        classification_result = DocumentExtractionService.classify_document(combined_text)
        
        document.detected_type = classification_result['detected_type']
        
        # Prefer Gemini's average confidence if available
        avg_conf = sum(p.page_detection_confidence for p in pages if p.page_detection_confidence) / max(1, len(pages))
        document.confidence_score = avg_conf if avg_conf > 0 else classification_result['confidence_score']
        
        if not document.extracted_data:
            document.extracted_data = classification_result['extracted_data']

        # 5. Type mismatch check — was the uploaded file the right document type?
        detected = classification_result['detected_type']
        declared = document.document_type
        type_mismatch = (
            detected not in ('unknown', 'other')
            and detected != declared
        )
        if type_mismatch:
            mismatch_msg = (
                f"Document uploaded as '{declared}' but content appears to be '{detected}'. "
                f"Please re-upload the correct document."
            )
            ComplianceSignal.objects.get_or_create(
                vendor=document.vendor,
                document=document,
                signal_type='document_type_mismatch',
                defaults={
                    'description': mismatch_msg,
                    'source': 'OCR'
                }
            )
            validation_notes.append(f"⚠ Type mismatch: declared as '{declared}', content detected as '{detected}'.")

        document.classification_metadata = {
            'detected_type': classification_result['detected_type'],
            'confidence': float(classification_result['confidence_score']),
            'detected_pages': list(unique_pages),
            'unidentified_pages': unidentified_count,
            'validation_notes': validation_notes,
            'type_mismatch': type_mismatch,
        }

        # 6. Store validation notes
        existing = document.validation_results or {}
        if validation_notes:
            existing['ocr_notes'] = validation_notes
        if type_mismatch:
            existing['type_mismatch'] = True
            existing['type_mismatch_message'] = mismatch_msg
        document.validation_results = existing

        document.ocr_status = 'completed'

        # 7. Auto-Resubmit vs Pending Review
        if auto_resubmit:
            document.status = Document.STATUS_RESUBMISSION
            document.review_notes = resubmit_reason
            
            # Notify Vendor
            from apps.notifications.models import Notification
            if document.vendor and document.vendor.user:
                Notification.objects.create(
                    recipient=document.vendor.user,
                    notification_type=Notification.TYPE_WARNING,
                    title="Action Required: Contract Resubmission",
                    message=resubmit_reason,
                    link="/vendor/documents"
                )
        else:
            document.status = Document.STATUS_PENDING
        
        document.save(update_fields=[
            'status', 'ocr_status', 'raw_ocr_text', 'detected_type',
            'confidence_score', 'extracted_data', 'classification_metadata',
            'validation_results', 'review_notes'
        ])
        
    except Document.DoesNotExist:
        pass
    except Exception as e:
        print(f"Error processing document {document_id}: {e}")
        import traceback
        traceback.print_exc()
        try:
            document = Document.objects.get(id=document_id)
            document.ocr_status = 'failed'
            # Still send to admin — don't leave vendor hanging
            document.status = Document.STATUS_PENDING
            document.save(update_fields=['ocr_status', 'status'])
        except:
            pass
