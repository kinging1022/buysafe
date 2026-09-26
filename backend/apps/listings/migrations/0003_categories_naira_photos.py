"""Categories become a table, prices move to whole naira, ListingImage becomes
ListingPhoto, and condition/description become required.

Existing rows are converted, not dropped:
- price_kobo -> price (÷ 100, rounded half up)
- the old text category -> the matching Category row, else "Other"
- blank condition -> "good"; blank description -> "No description yet."
Backfilled rows are printed while migrating so they can be reviewed.
"""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

from apps.users.states import NG_STATES

CATEGORIES = [
    ("Phones & tablets", "phones-tablets"),
    ("Laptops & computers", "laptops-computers"),
    ("Home appliances", "home-appliances"),
    ("Furniture", "furniture"),
    ("TVs & audio", "tvs-audio"),
    ("Gaming", "gaming"),
    ("Generators & power", "generators-power"),
    ("Baby & kids", "baby-kids"),
    ("Kitchen", "kitchen"),
    ("Fashion", "fashion"),
    ("Sports & fitness", "sports-fitness"),
    ("Other", "other"),
]

# The text values from 0002 -> the new slugs.
OLD_TO_SLUG = {
    "phones": "phones-tablets",
    "computers": "laptops-computers",
    "appliances": "home-appliances",
    "furniture": "furniture",
    "power": "generators-power",
    "baby": "baby-kids",
    "tv_audio": "tvs-audio",
    "gaming": "gaming",
    "sport": "sports-fitness",
    "other": "other",
}

DESCRIPTION_PLACEHOLDER = "No description yet."


def seed_categories(apps, schema_editor):
    Category = apps.get_model("listings", "Category")
    for order, (name, slug) in enumerate(CATEGORIES):
        Category.objects.update_or_create(slug=slug, defaults={"name": name, "sort_order": order, "is_active": True})


def convert_rows(apps, schema_editor):
    Listing = apps.get_model("listings", "Listing")
    Category = apps.get_model("listings", "Category")
    by_slug = {c.slug: c for c in Category.objects.all()}
    flagged = []
    for listing in Listing.objects.all():
        notes = []
        listing.price = (listing.price_kobo + 50) // 100
        slug = OLD_TO_SLUG.get(listing.category_old)
        if not slug:
            slug = "other"
            notes.append("category -> Other")
        listing.category = by_slug[slug]
        if not listing.condition:
            listing.condition = "good"
            notes.append("condition -> good")
        if not listing.description.strip():
            listing.description = DESCRIPTION_PLACEHOLDER
            notes.append("description -> placeholder")
        listing.area_normalized = " ".join(listing.area.split()).lower()
        listing.save()
        if notes:
            flagged.append(f"  listing {listing.pk} ({listing.title}): {', '.join(notes)}")
    if flagged:
        print("\n  Backfilled listings to review:\n" + "\n".join(flagged))


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0002_category_condition_description"),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60)),
                ("slug", models.SlugField(max_length=60, unique=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["sort_order", "name"], "verbose_name_plural": "categories"},
        ),
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
        # Photos
        migrations.RenameModel("ListingImage", "ListingPhoto"),
        migrations.AlterField(
            model_name="listingphoto",
            name="listing",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name="photos", to="listings.listing"
            ),
        ),
        migrations.AddField(
            model_name="listingphoto",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # New columns, nullable while rows are converted
        migrations.RenameField("listing", "category", "category_old"),
        migrations.AddField(
            model_name="listing",
            name="category",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="listings", to="listings.category"
            ),
        ),
        migrations.AddField(model_name="listing", name="price", field=models.PositiveIntegerField(null=True)),
        migrations.AddField(
            model_name="listing",
            name="area_normalized",
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=60),
        ),
        migrations.RunPython(convert_rows, migrations.RunPython.noop),
        migrations.RemoveField(model_name="listing", name="category_old"),
        migrations.RemoveField(model_name="listing", name="price_kobo"),
        migrations.AlterField(
            model_name="listing",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="listings", to="listings.category"
            ),
        ),
        migrations.AlterField(model_name="listing", name="price", field=models.PositiveIntegerField()),
        migrations.AlterField(
            model_name="listing",
            name="condition",
            field=models.CharField(
                choices=[
                    ("brand_new", "Brand new"),
                    ("like_new", "Like new"),
                    ("good", "Good"),
                    ("fair", "Fair"),
                    ("for_parts", "For parts"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(model_name="listing", name="description", field=models.TextField(max_length=1000)),
        migrations.AlterField(
            model_name="listing",
            name="state",
            field=models.CharField(
                blank=True, choices=NG_STATES, db_index=True, max_length=20
            ),
        ),
        migrations.AddIndex(
            model_name="listing",
            index=models.Index(fields=["approval_status", "is_deleted", "-created_at"], name="listing_public_idx"),
        ),
        migrations.AddIndex(
            model_name="listing", index=models.Index(fields=["price"], name="listing_price_idx"),
        ),
    ]
