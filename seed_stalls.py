import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.vendors.models import Stall, MarketSection

def seed():
    print("Seeding Main Building Stalls...")
    
    # Get or create a default section just so the model doesn't fail on foreign key
    section, _ = MarketSection.objects.get_or_create(
        code="DEF",
        defaults={"name": "Default Section", "building": "main", "floor": "1"}
    )

    # Naming convention definitions: { "Prefix": (start, end) }
    ranges_1st_floor = {
        # Left side
        "A-": (1, 5),
        "B-": (1, 4),
        # Fish section
        "C-": (1, 7),
        "D-": (1, 7),
        "E-": (1, 7),
        "F-": (1, 21),
        "G-": (1, 21),
        "H-": (1, 21),
        "I-": (1, 21),
        "J-": (1, 21),
    }
    
    created_count = 0
    
    for prefix, (start, end) in ranges_1st_floor.items():
        for i in range(start, end + 1):
            # Pad with 0? The DB currently has A-01, but the image says A-1. Let's use whatever format they prefer.
            # I will generate both "A-1" format to match the image, but the DB has "A-01". Let's use exactly what's in the DB if it exists, otherwise use A-01 format to be safe and consistent.
            stall_number = f"{prefix}{i:02d}"
            
            stall, created = Stall.objects.get_or_create(
                stall_number=stall_number,
                defaults={
                    "section": section,
                    "building": "main",
                    "floor": "1",
                    "category": "Unassigned",
                }
            )
            if created:
                created_count += 1

    print(f"Created {created_count} stalls on the 1st floor.")

if __name__ == "__main__":
    seed()
