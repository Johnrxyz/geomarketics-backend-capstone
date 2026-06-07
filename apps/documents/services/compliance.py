from apps.documents.models import Document, ComplianceSignal
from apps.documents.services.consistency import VendorConsistencyService

class VendorComplianceService:
    @staticmethod
    def evaluate_vendor(vendor):
        """
        Dynamically calculates the compliance status, risk score, and risk level.
        Returns a reusable JSON-serializable dictionary for dashboard consumption.
        """
        # Ensure consistency signals are up to date
        VendorConsistencyService.evaluate_vendor(vendor)

        # Retrieve required documents
        bp = Document.objects.filter(vendor=vendor, document_type=Document.TYPE_BUSINESS_PERMIT).order_by('-created_at').first()
        contract = Document.objects.filter(vendor=vendor, document_type=Document.TYPE_CONTRACT).order_by('-created_at').first()

        risk_score = 0
        signals = list(ComplianceSignal.objects.filter(vendor=vendor).values('signal_type', 'description', 'source', 'created_at'))
        
        # We also generate system-level dynamic signals based on current document states
        dynamic_signals = []

        is_bp_verified = bp and bp.status == Document.STATUS_APPROVED
        is_contract_verified = contract and contract.status == Document.STATUS_APPROVED

        # 1. Missing Required Documents (+30)
        if not bp:
            risk_score += 30
            dynamic_signals.append({'signal_type': 'missing_permit', 'description': 'No Business Permit on file', 'source': 'SYSTEM'})
        elif bp.status == Document.STATUS_EXPIRED:
            # Expired Permit (+50)
            risk_score += 50
            dynamic_signals.append({'signal_type': 'expired_permit', 'description': 'Business Permit is expired', 'source': 'SYSTEM'})
        elif not is_bp_verified:
            # Processing / Pending (+10)
            risk_score += 10
            dynamic_signals.append({'signal_type': 'unverified_permit', 'description': 'Business Permit is not verified yet', 'source': 'SYSTEM'})

        if not contract:
            risk_score += 30
            dynamic_signals.append({'signal_type': 'missing_contract', 'description': 'No Contract on file', 'source': 'SYSTEM'})
        elif not is_contract_verified:
            risk_score += 10
            dynamic_signals.append({'signal_type': 'unverified_contract', 'description': 'Contract is not verified yet', 'source': 'SYSTEM'})

        # 2. Add points from persisted ComplianceSignals
        for sig in signals:
            if sig['signal_type'] in ['mismatch_owner', 'mismatch_business', 'mismatch_stall']:
                risk_score += 20
            elif sig['signal_type'] in ['invalid_contract_page', 'ocr_failure']:
                risk_score += 10
            else:
                risk_score += 10 # Default for other warnings

        # 3. Determine Overall Status
        compliance_status = "Non-Compliant"
        if is_bp_verified and is_contract_verified:
            # Fully Compliant ONLY when both are verified
            # We allow warnings to exist, but they affect risk score, not baseline compliance
            compliance_status = "Compliant"

        # 4. Determine Risk Level
        if risk_score >= 50:
            risk_level = "High"
        elif risk_score >= 20:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Combine dynamic and persisted signals for the final payload
        all_signals = dynamic_signals + signals

        return {
            "compliance_status": compliance_status,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "signals": all_signals
        }
