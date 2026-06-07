from apps.documents.models import Document, ComplianceSignal

class VendorConsistencyService:
    @staticmethod
    def evaluate_vendor(vendor):
        """
        Dynamically compares extracted data across a vendor's active documents.
        Generates granular ComplianceSignals for any mismatches detected.
        Returns a dictionary of validation results.
        """
        # Fetch the latest relevant documents for the vendor
        business_permit = Document.objects.filter(
            vendor=vendor, 
            document_type=Document.TYPE_BUSINESS_PERMIT,
            status__in=[Document.STATUS_APPROVED, Document.STATUS_PENDING, Document.STATUS_EXPIRED]
        ).order_by('-created_at').first()
        
        contract = Document.objects.filter(
            vendor=vendor, 
            document_type=Document.TYPE_CONTRACT,
            status__in=[Document.STATUS_APPROVED, Document.STATUS_PENDING, Document.STATUS_EXPIRED]
        ).order_by('-created_at').first()

        results = {
            'owner_match': True,
            'business_match': True,
            'stall_match': True,
            'details': []
        }

        # Clear previous validation signals for this vendor to ensure fresh dynamic state
        ComplianceSignal.objects.filter(vendor=vendor, source=ComplianceSignal.SOURCE_VALIDATION).delete()

        if not business_permit or not contract:
            results['details'].append("Insufficient documents for consistency validation.")
            return results

        bp_data = business_permit.extracted_data or {}
        contract_data = contract.extracted_data or {}

        # 1. Compare Owner Name (Business Permit vs Contract)
        bp_owner = bp_data.get('owner_name', '').strip().lower()
        contract_vendor = contract_data.get('vendor_name', '').strip().lower()
        
        if bp_owner and contract_vendor and bp_owner != contract_vendor:
            results['owner_match'] = False
            results['details'].append(f"Owner mismatch: '{bp_owner}' vs '{contract_vendor}'")
            ComplianceSignal.objects.create(
                vendor=vendor,
                signal_type='mismatch_owner',
                description=f"Business Permit owner '{bp_owner}' does not match Contract vendor '{contract_vendor}'",
                source=ComplianceSignal.SOURCE_VALIDATION
            )

        # 2. Compare Business Name (Business Permit vs Contract)
        # Assuming contract might also extract business name if present in future
        bp_biz = bp_data.get('business_name', '').strip().lower()
        contract_biz = contract_data.get('business_name', '').strip().lower()
        
        if bp_biz and contract_biz and bp_biz != contract_biz:
            results['business_match'] = False
            results['details'].append(f"Business mismatch: '{bp_biz}' vs '{contract_biz}'")
            ComplianceSignal.objects.create(
                vendor=vendor,
                signal_type='mismatch_business',
                description=f"Business Permit name '{bp_biz}' does not match Contract business name '{contract_biz}'",
                source=ComplianceSignal.SOURCE_VALIDATION
            )

        # 3. Compare Stall Number (Contract vs Vendor Model)
        contract_stall = contract_data.get('normalized_stall_number')
        vendor_stall = vendor.stall.stall_number if vendor.stall else None
        
        if contract_stall and vendor_stall and contract_stall != vendor_stall:
            results['stall_match'] = False
            results['details'].append(f"Stall mismatch: Contract '{contract_stall}' vs System '{vendor_stall}'")
            ComplianceSignal.objects.create(
                vendor=vendor,
                signal_type='mismatch_stall',
                description=f"Contract stall number '{contract_stall}' does not match assigned stall '{vendor_stall}'",
                source=ComplianceSignal.SOURCE_VALIDATION
            )

        return results
