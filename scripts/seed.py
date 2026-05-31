"""
Seed script for LC Public Market system.
Run: python manage.py shell < scripts/seed.py
Or:  python scripts/seed.py (from backend directory with DJANGO_SETTINGS_MODULE set)
"""
import os
import sys
import django
from datetime import date, timedelta

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.users.models import User
from apps.vendors.models import MarketSection, Stall, Vendor
from apps.complaints.models import Complaint
from apps.documents.models import Document
from apps.sanitation.models import SanitationCheckItem, SanitationSession, SanitationRecord
from apps.prices.models import CommodityCategory, Commodity, PriceReport, PriceEntry
from apps.notifications.models import Notification

print("🌱 Starting seed...")

# ─── USERS ───────────────────────────────────────────────────────────────────

admin_user, _ = User.objects.get_or_create(
    username='admin',
    defaults={
        'email': 'admin@lcmarket.gov.ph',
        'first_name': 'Market',
        'last_name': 'Administrator',
        'role': 'admin',
        'is_staff': True,
        'is_superuser': True,
    }
)
admin_user.set_password('admin123')
admin_user.save()
print(f"  ✓ Admin: admin / admin123")

# Vendor users
vendor_users_data = [
    ('maria.santos', 'Maria', 'Santos', 'maria@example.com', '09171234501'),
    ('luis.reyes', 'Luis', 'Reyes', 'luis@example.com', '09171234502'),
    ('juan.delacruz', 'Juan', 'dela Cruz', 'juan@example.com', '09171234503'),
    ('pedro.garcia', 'Pedro', 'Garcia', 'pedro@example.com', '09171234504'),
    ('ana.torres', 'Ana', 'Torres', 'ana@example.com', '09171234505'),
    ('rosa.navarro', 'Rosa', 'Navarro', 'rosa@example.com', '09171234506'),
    ('carlo.mendoza', 'Carlo', 'Mendoza', 'carlo@example.com', '09171234507'),
    ('elena.flores', 'Elena', 'Flores', 'elena@example.com', '09171234508'),
    ('ben.castillo', 'Ben', 'Castillo', 'ben@example.com', '09171234509'),
    ('nena.cruz', 'Nena', 'Cruz', 'nena@example.com', '09171234510'),
    ('tony.ramos', 'Tony', 'Ramos', 'tony@example.com', '09171234511'),
    ('linda.reyes', 'Linda', 'Reyes', 'linda@example.com', '09171234512'),
    ('mark.santos', 'Mark', 'Santos', 'mark@example.com', '09171234513'),
    ('grace.dela', 'Grace', 'dela Vega', 'grace@example.com', '09171234514'),
    ('jose.aquino', 'Jose', 'Aquino', 'jose@example.com', '09171234515'),
]

vendor_user_objs = {}
for uname, fn, ln, em, ph in vendor_users_data:
    u, _ = User.objects.get_or_create(
        username=uname,
        defaults={'email': em, 'first_name': fn, 'last_name': ln, 'role': 'vendor', 'phone': ph}
    )
    u.set_password('vendor123')
    u.save()
    vendor_user_objs[uname] = u

# Customer user
customer, _ = User.objects.get_or_create(
    username='customer',
    defaults={
        'email': 'customer@example.com',
        'first_name': 'Sample',
        'last_name': 'Customer',
        'role': 'customer',
    }
)
customer.set_password('customer123')
customer.save()
print(f"  ✓ Vendor accounts: vendor123 | Customer: customer / customer123")

# ─── MARKET SECTIONS ────────────────────────────────────────────────────────

sections_data = [
    ('A', 'Vegetables', 'Fresh vegetables and produce', '#22c55e'),
    ('B', 'Meat', 'Poultry, pork, beef, and other meats', '#ef4444'),
    ('C', 'Fish & Seafood', 'Fresh fish and seafood products', '#3b82f6'),
    ('D', 'Dry Goods', 'Rice, grains, canned goods, and dry commodities', '#f59e0b'),
    ('E', 'Cooked Food', 'Ready-to-eat and cooked food stalls', '#8b5cf6'),
    ('F', 'Fruits', 'Fresh seasonal and imported fruits', '#ec4899'),
]

section_objs = {}
for code, name, desc, color in sections_data:
    s, _ = MarketSection.objects.get_or_create(code=code, defaults={'name': name, 'description': desc, 'color': color})
    section_objs[code] = s
print(f"  ✓ {len(section_objs)} market sections")

# ─── STALLS ─────────────────────────────────────────────────────────────────

stalls_data = [
    # stall_number, section_code, category, status, area, rent, map_x, map_y, map_w, map_h
    ('A-01', 'A', 'Vegetables', 'occupied', 12.5, 1800, 50, 100, 80, 60),
    ('A-02', 'A', 'Vegetables', 'vacant',   12.5, 1800, 140, 100, 80, 60),
    ('A-03', 'A', 'Vegetables', 'occupied', 10.0, 1600, 230, 100, 80, 60),
    ('A-04', 'A', 'Vegetables', 'occupied', 10.0, 1600, 320, 100, 80, 60),
    ('B-01', 'B', 'Meat',       'occupied', 15.0, 2200, 50, 200, 80, 60),
    ('B-02', 'B', 'Meat',       'vacant',   15.0, 2200, 140, 200, 80, 60),
    ('B-03', 'B', 'Meat',       'occupied', 12.5, 2000, 230, 200, 80, 60),
    ('B-12', 'B', 'Meat',       'flagged',  12.5, 2000, 320, 200, 80, 60),
    ('C-01', 'C', 'Fish',       'occupied', 14.0, 2100, 50, 300, 80, 60),
    ('C-02', 'C', 'Fish',       'occupied', 14.0, 2100, 140, 300, 80, 60),
    ('C-03', 'C', 'Fish',       'vacant',   12.0, 1900, 230, 300, 80, 60),
    ('D-01', 'D', 'Dry Goods',  'occupied', 18.0, 2500, 50, 400, 100, 60),
    ('D-02', 'D', 'Dry Goods',  'reserved', 18.0, 2500, 160, 400, 100, 60),
    ('E-01', 'E', 'Cooked Food','occupied', 16.0, 2300, 50, 500, 90, 60),
    ('E-02', 'E', 'Cooked Food','occupied', 16.0, 2300, 150, 500, 90, 60),
]

stall_objs = {}
for snum, sec_code, cat, sts, area, rent, mx, my, mw, mh in stalls_data:
    s, _ = Stall.objects.get_or_create(
        stall_number=snum,
        defaults={
            'section': section_objs[sec_code],
            'category': cat,
            'status': sts,
            'area_sqm': area,
            'monthly_rent': rent,
            'map_x': mx, 'map_y': my, 'map_width': mw, 'map_height': mh,
        }
    )
    stall_objs[snum] = s
print(f"  ✓ {len(stall_objs)} stalls")

# ─── VENDORS ────────────────────────────────────────────────────────────────

vendors_data = [
    # username, stall_number, products, permit_num, permit_expiry, health_cert_expiry, compliance, joined
    ('maria.santos',   'A-01', 'Ampalaya, Kangkong, Sitaw, Okra, Talong', 'BP-2026-001', date(2026,12,31), date(2026,6,30), 95.0, date(2020,1,15)),
    ('luis.reyes',     'A-03', 'Kamatis, Sili, Pechay, Mustasa', 'BP-2026-003', date(2026,12,31), date(2026,9,30), 88.0, date(2019,3,20)),
    ('juan.delacruz',  'A-04', 'Labanos, Singkamas, Patola, Upo', 'BP-2026-004', date(2026,12,31), date(2026,6,30), 75.0, date(2021,6,1)),
    ('pedro.garcia',   'B-01', 'Pork Liempo, Pork Kasim, Pork Ribs', 'BP-2026-005', date(2026,12,31), date(2026,6,30), 92.0, date(2018,2,14)),
    ('ana.torres',     'B-03', 'Chicken Whole, Chicken Cuts, Chicken Liver', 'BP-2026-007', date(2026,12,31), date(2026,9,30), 85.0, date(2020,8,5)),
    ('rosa.navarro',   'B-12', 'Beef Kasim, Beef Brisket, Beef Liver', 'BP-2026-008', date(2025,12,31), date(2025,12,31), 60.0, date(2017,11,20)),
    ('carlo.mendoza',  'C-01', 'Bangus, Tilapia, Galunggong, Talakitok', 'BP-2026-009', date(2026,12,31), date(2026,6,30), 90.0, date(2019,7,12)),
    ('elena.flores',   'C-02', 'Hipon, Pusit, Alimasag, Tahong', 'BP-2026-010', date(2026,12,31), date(2026,9,30), 87.0, date(2022,1,8)),
    ('ben.castillo',   'D-01', 'Regular Rice, Premium Rice, Corn Grits, Sugar', 'BP-2026-012', date(2026,12,31), date(2026,6,30), 98.0, date(2016,5,30)),
    ('nena.cruz',      'E-01', 'Arroz Caldo, Goto, Lugaw, Silog Meals', 'BP-2026-014', date(2026,12,31), date(2026,9,30), 82.0, date(2021,2,14)),
    ('tony.ramos',     'E-02', 'Fried Chicken, Grilled Pork, Pancit, Adobo', 'BP-2026-015', date(2026,12,31), date(2026,6,30), 79.0, date(2020,9,3)),
]

vendor_objs = {}
for uname, stall_num, prods, pnum, pexp, hexp, comp, joined in vendors_data:
    u = vendor_user_objs[uname]
    v, _ = Vendor.objects.get_or_create(
        user=u,
        defaults={
            'stall': stall_objs[stall_num],
            'first_name': u.first_name,
            'last_name': u.last_name,
            'email': u.email,
            'phone': u.phone,
            'products': prods,
            'permit_number': pnum,
            'permit_expiry': pexp,
            'health_cert_expiry': hexp,
            'compliance_rate': comp,
            'joined_at': joined,
            'is_active': True,
        }
    )
    vendor_objs[stall_num] = v
print(f"  ✓ {len(vendor_objs)} vendors")

# ─── COMPLAINTS ─────────────────────────────────────────────────────────────

complaints_data = [
    ('B-12', 'Unsanitary meat display conditions observed', 'sanitation',
     'The meat display area has visible blood residue and lacks proper drainage. Health risk to consumers.',
     'open', '', customer),
    ('A-04', 'Overpricing of vegetables beyond SRP', 'overpricing',
     'Vendor is selling vegetables at 40% above the suggested retail price without justification.',
     'reviewing', 'Vendor was informed. Price monitoring scheduled.', customer),
    ('C-03', 'Blocking emergency exit passageway', 'safety',
     'Fish vendor has placed display boxes blocking the emergency exit near Section C.',
     'resolved', 'Issue resolved. Vendor moved display. Follow-up inspection passed.', customer),
    ('E-01', 'Food safety concern - no temperature control', 'food_safety',
     'Cooked food left unrefrigerated for more than 4 hours. Possible spoilage risk.',
     'open', '', customer),
    ('A-01', 'Produce display spilling into walkway', 'display',
     'Vegetable vendor has produce stacked in the customer walkway area, obstructing foot traffic.',
     'reviewing', 'Warning issued. Monitoring in progress.', None),
    ('D-01', 'Business permit appears expired', 'permit',
     'Permit sticker posted appears to be from 2024. Cannot verify current validity.',
     'resolved', 'Vendor presented valid 2026 permit. False alarm.', None),
]

today = date.today()
for i, (stall_num, subj, cat, desc, sts, notes, complainant) in enumerate(complaints_data):
    stall = stall_objs.get(stall_num)
    vendor = vendor_objs.get(stall_num) if stall_num in vendor_objs else None
    c, _ = Complaint.objects.get_or_create(
        subject=subj,
        defaults={
            'vendor': vendor,
            'stall': stall,
            'category': cat,
            'description': desc,
            'status': sts,
            'admin_notes': notes,
            'complainant': complainant,
            'complainant_name': '' if complainant else 'Anonymous',
        }
    )
print(f"  ✓ {len(complaints_data)} complaints")

# ─── DOCUMENTS ───────────────────────────────────────────────────────────────

docs_data = [
    ('BP-2026-001', 'business_permit', vendor_objs.get('A-01'), 'pending', date(2026,12,31)),
    ('BP-2026-003', 'business_permit', vendor_objs.get('A-03'), 'approved', date(2026,12,31)),
    ('BP-2026-005', 'business_permit', vendor_objs.get('B-01'), 'approved', date(2026,12,31)),
    ('SanCert-2026-001', 'sanitation_cert', vendor_objs.get('A-01'), 'approved', date(2026,6,30)),
    ('RentRcpt-Apr2026', 'rent_receipt', vendor_objs.get('B-12'), 'pending', None),
    ('RentRcpt-May2026', 'rent_receipt', vendor_objs.get('C-01'), 'approved', None),
    ('HealthCert-2026-007', 'health_cert', vendor_objs.get('B-03'), 'pending', date(2026,9,30)),
    ('TaxClear-2026-012', 'tax_clearance', vendor_objs.get('D-01'), 'rejected', date(2026,12,31)),
]

for title, dtype, vendor, sts, exp in docs_data:
    if vendor:
        Document.objects.get_or_create(
            title=title,
            defaults={
                'vendor': vendor,
                'document_type': dtype,
                'status': sts,
                'expiry_date': exp,
            }
        )
print(f"  ✓ {len(docs_data)} documents")

# ─── SANITATION CHECK ITEMS ──────────────────────────────────────────────────

check_items_data = [
    ('id_verification', 'ID Verification', 0),
    ('uniform', 'Proper Uniform', 1),
    ('hair_net', 'Hair Net / Head Cover', 2),
    ('apron', 'Clean Apron', 3),
    ('boots', 'Proper Footwear / Boots', 4),
    ('mask', 'Spit Guard / Face Mask', 5),
    ('business_permit', 'Business Permit Displayed', 6),
]

item_objs = {}
for name, label, order in check_items_data:
    item, _ = SanitationCheckItem.objects.get_or_create(
        name=name, defaults={'label': label, 'order': order}
    )
    item_objs[name] = item
print(f"  ✓ {len(item_objs)} sanitation check items")

# ─── SANITATION SESSION (sample) ─────────────────────────────────────────────

session, created = SanitationSession.objects.get_or_create(
    date=today,
    section=section_objs['A'],
    defaults={'conducted_by': admin_user, 'notes': 'Regular weekly inspection'}
)

# Create sample records for section A vendors
status_cycle = ['pass', 'pass', 'fail', 'pass', 'pass', 'pass', 'pass']
for stall_key in ['A-01', 'A-03', 'A-04']:
    v = vendor_objs.get(stall_key)
    if v:
        for i, (iname, _, _) in enumerate(check_items_data):
            SanitationRecord.objects.get_or_create(
                session=session,
                vendor=v,
                check_item=item_objs[iname],
                defaults={'status': status_cycle[i % len(status_cycle)], 'remarks': ''}
            )

session.compliance_rate = session.calculate_compliance()
session.save()
print(f"  ✓ Sanitation session created for Section A")

# ─── COMMODITY CATEGORIES & COMMODITIES ──────────────────────────────────────

categories_data = [
    ('I',    'Imported Rice', [('Premium Jasmine Rice', 'kg', 75), ('Well-Milled Rice', 'kg', 65)]),
    ('II',   'Local Rice',    [('Regular Milled Rice', 'kg', 52), ('Special Local Rice', 'kg', 58), ('Dinorado', 'kg', 62)]),
    ('III',  'Corn',          [('Corn (White)', 'kg', 45), ('Corn (Yellow)', 'kg', 42)]),
    ('IV',   'Meat',          [
        ('Pork Kasim', 'kg', 280), ('Pork Liempo', 'kg', 320), ('Pork Ribs', 'kg', 310),
        ('Beef Kasim', 'kg', 380), ('Beef Brisket', 'kg', 350), ('Whole Chicken', 'kg', 185),
        ('Chicken Leg Quarters', 'kg', 160), ('Eggs (Native)', 'piece', 10),
    ]),
    ('V',    'Fish & Seafood', [
        ('Bangus (Milkfish)', 'kg', 180), ('Tilapia', 'kg', 120), ('Galunggong', 'kg', 160),
        ('Hipon (Shrimp)', 'kg', 350), ('Pusit (Squid)', 'kg', 280), ('Tahong (Mussels)', 'kg', 100),
        ('Talakitok', 'kg', 200),
    ]),
    ('VI',   'Vegetables', [
        ('Ampalaya', 'kg', 80), ('Kangkong', 'bundle', 20), ('Sitaw', 'kg', 60),
        ('Kamatis', 'kg', 70), ('Sili (Green)', 'kg', 120), ('Pechay', 'kg', 50),
        ('Talong', 'kg', 55), ('Upo', 'piece', 30), ('Labanos', 'kg', 45),
        ('Patola', 'piece', 25), ('Sigarilyas', 'kg', 70), ('Okra', 'kg', 65),
    ]),
    ('VII',  'Fruits', [
        ('Saging (Lakatan)', 'kg', 90), ('Mangga (Carabao)', 'kg', 110),
        ('Papaya', 'kg', 50), ('Pinya', 'piece', 60), ('Suha', 'piece', 45), ('Dalandan', 'kg', 70),
    ]),
    ('VIII', 'Cooking Oil & Fats', [
        ('Cooking Oil (Refined)', 'liter', 85), ('Palm Oil', 'liter', 75), ('Coconut Oil', 'liter', 95),
    ]),
    ('IX',   'Sugar', [
        ('White Sugar', 'kg', 72), ('Brown Sugar', 'kg', 68), ('Muscovado', 'kg', 80),
    ]),
    ('X',    'Canned Goods', [
        ('Sardines (Tomato Sauce)', 'can', 22), ('Corned Beef (175g)', 'can', 48),
        ('Tuna in oil', 'can', 38),
    ]),
    ('XI',   'Condiments', [
        ('Patis (Fish Sauce) 350ml', 'pack', 35), ('Toyo (Soy Sauce) 350ml', 'pack', 28),
        ('Suka (Vinegar) 350ml', 'pack', 22), ('Asin (Salt) 1kg', 'pack', 20),
        ('Magic Sarap 8g', 'pack', 8),
    ]),
]

cat_objs = {}
commodity_objs = {}
for i, (roman, cname, items) in enumerate(categories_data):
    cat, _ = CommodityCategory.objects.get_or_create(name=cname, defaults={'roman_numeral': roman, 'order': i})
    cat_objs[cname] = cat
    for j, (iname, unit, price) in enumerate(items):
        c, _ = Commodity.objects.get_or_create(
            name=iname, category=cat,
            defaults={'unit': unit, 'standard_price': price, 'order': j}
        )
        commodity_objs[iname] = c

total_commodities = Commodity.objects.count()
print(f"  ✓ {len(cat_objs)} categories, {total_commodities} commodities")

# ─── PRICE REPORT (sample) ───────────────────────────────────────────────────

report, created = PriceReport.objects.get_or_create(
    report_date=today,
    defaults={
        'submitted_by': admin_user,
        'period_label': f'Week of {today.strftime("%B %d, %Y")}',
        'is_published': True,
        'notes': 'Weekly price monitoring report.',
    }
)

import decimal
import random
random.seed(42)

for cname, commodity in commodity_objs.items():
    base = float(commodity.standard_price or 50)
    prices = [round(base * random.uniform(0.92, 1.10), 2) for _ in range(5)]
    PriceEntry.objects.get_or_create(
        report=report,
        commodity=commodity,
        defaults={
            'respondent_1': prices[0], 'respondent_2': prices[1], 'respondent_3': prices[2],
            'respondent_4': prices[3], 'respondent_5': prices[4],
            'previous_price': round(base * random.uniform(0.95, 1.05), 2),
            'remark': random.choice(['stable', 'stable', 'stable', 'high', 'low']),
        }
    )
print(f"  ✓ Price report created for {today}")

# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────

notifs = [
    (admin_user, 'warning', 'Documents Pending Review', '5 vendor documents are awaiting review.', '/admin/documents'),
    (admin_user, 'error', 'Low Compliance Alert', '3 vendors below 70% sanitation compliance.', '/admin/sanitation'),
    (admin_user, 'info', 'Monthly Report Due', 'May 2026 monthly report is due by end of month.', '/admin/reports'),
]

for user, ntype, title, msg, link in notifs:
    Notification.objects.get_or_create(
        recipient=user, title=title,
        defaults={'notification_type': ntype, 'message': msg, 'link': link}
    )
print(f"  ✓ {len(notifs)} notifications")

print("\n✅ Seed complete!")
print("\n📋 Login credentials:")
print("   Admin:    admin / admin123")
print("   Vendor:   maria.santos / vendor123")
print("   Vendor:   pedro.garcia / vendor123")
print("   Customer: customer / customer123")
