import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.vendors.models import Stall, MarketSection

def seed():
    print("Seeding Main Building Stalls...")
    
    # Get or create a default section just so the model doesn't fail on foreign key
    section, _ = MarketSection.objects.get_or_create(
        code="DEF",
        defaults={"name": "Default Section"}
    )

    # Naming convention definitions: { "Prefix": ((start, end), section_code, section_name, category) }
    ranges_1st_floor = {
        "A-": ((1, 10), "FISH", "Fish Section", "Fish"),
        "B-": ((1, 15), "FISH", "Fish Section", "Fish"),
        "C-": ((1, 10), "FISH", "Fish Section", "Fish"),
        "D-": ((1, 10), "FISH", "Fish Section", "Fish"),
        "E-": ((1, 10), "FISH", "Fish Section", "Fish"),
        "F-": ((1, 21), "FISH", "Fish Section", "Fish"),
        "G-": ((1, 21), "FISH", "Fish Section", "Fish"),
        "H-": ((1, 21), "FISH", "Fish Section", "Fish"),
        "I-": ((1, 21), "FISH", "Fish Section", "Fish"),
        "J-": ((1, 21), "FISH", "Fish Section", "Fish"),
    }
    
    ranges_2nd_floor = {
        "SA-": ((1, 50), "SARI", "Sari-Sari Section", "Sari-Sari"),
        "M-":  ((1, 35), "MEAT", "Meat Section", "Meat"),
        "SF-": ((1, 20), "SMKD", "Smoked Fish Section", "Smoked Fish"),
        "FW-": ((1, 20), "FOOT", "Footwear Section", "Footwear"),
        "FZ-": ((1, 15), "FRZN", "Frozen Section", "Frozen"),
        "P-":  ((1, 15), "PASAL", "Pasalubong Section", "Pasalubong"),
        "PR-": ((1, 15), "PARLOR", "Parlor Section", "Parlor"),
    }
    
    created_count = 0
    updated_count = 0
    
    def process_stalls(ranges, floor_num):
        nonlocal created_count, updated_count
        for prefix, ((start, end), sec_code, sec_name, category) in ranges.items():
            # Get or create the mapped section
            section_obj, _ = MarketSection.objects.get_or_create(
                code=sec_code,
                defaults={"name": sec_name}
            )
            
            for i in range(start, end + 1):
                stall_number = f"{prefix}{i:02d}"
                stall, created = Stall.objects.get_or_create(
                    stall_number=stall_number,
                    defaults={
                        "section": section_obj,
                        "building": "main",
                        "floor": floor_num,
                        "category": category,
                    }
                )
                if created:
                    created_count += 1
                else:
                    # Update existing stalls to have the correct category/section (since they were created as Default)
                    if stall.section != section_obj or stall.category != category or stall.floor != floor_num:
                        stall.section = section_obj
                        stall.category = category
                        stall.floor = floor_num
                        stall.save()
                        updated_count += 1

    # Process floors
    process_stalls(ranges_1st_floor, "1")
    process_stalls(ranges_2nd_floor, "2")

    print(f"Successfully created {created_count} new stalls and updated {updated_count} existing stalls!")

if __name__ == "__main__":
    seed()
