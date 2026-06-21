from datetime import date, timedelta
from django.utils import timezone
from apps.analytics.models import AIRiskProfile


def compute_risk_for_vendor(vendor):
    """Transparent, explainable rule-based risk score from existing compliance signals.

    This is a weighted expert-system (NOT machine learning). Every contribution is
    recorded in `assessment_details` so the score is fully auditable and defensible.
    """
    today = date.today()
    breakdown = {}
    score = 0

    # 1) Active violations by severity (capped at 80)
    weights = {'critical': 40, 'high': 25, 'medium': 15, 'low': 5}
    actives = vendor.violations.filter(status='active')
    v_pts = min(sum(weights.get(v.severity, 15) for v in actives), 80)
    score += v_pts
    breakdown['violations'] = v_pts

    # 2) Unpaid penalties (capped at 30)
    unpaid = sum(1 for v in actives for p in v.penalties.all() if p.status == 'unpaid')
    p_pts = min(unpaid * 10, 30)
    score += p_pts
    breakdown['unpaid_penalties'] = p_pts

    # 3) Permit / health-cert expiry
    exp_pts = 0
    for d in (vendor.permit_expiry, vendor.health_cert_expiry):
        if d:
            if d < today:
                exp_pts += 20
            elif d <= today + timedelta(days=30):
                exp_pts += 10
    score += exp_pts
    breakdown['credentials'] = exp_pts

    # 4) Expired documents (capped at 30)
    doc_pts = min(vendor.documents.filter(status='expired').count() * 10, 30)
    score += doc_pts
    breakdown['expired_documents'] = doc_pts

    # 5) Open complaints (capped at 25)
    c_pts = min(vendor.complaints.filter(status='open').count() * 5, 25)
    score += c_pts
    breakdown['open_complaints'] = c_pts

    # 6) Sanitation compliance rate
    cr = float(vendor.compliance_rate or 100)
    s_pts = 20 if cr < 70 else (10 if cr <= 85 else 0)
    score += s_pts
    breakdown['sanitation'] = s_pts

    # Level thresholds
    level = 'high' if score >= 60 else ('medium' if score >= 30 else 'low')

    # Three-strike business rule (fixes R2): >= 3 active violations forces High
    active_count = actives.count()
    if active_count >= 3:
        level = 'high'
    breakdown['active_violation_count'] = active_count
    breakdown['three_strike_applied'] = active_count >= 3

    profile, _ = AIRiskProfile.objects.update_or_create(
        vendor=vendor,
        defaults={
            'risk_score': score,
            'risk_level': level,
            'assessment_details': breakdown,
            # last_assessment_date is auto_now=True -> updates on save
        },
    )
    return profile
