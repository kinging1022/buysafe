"""Transaction amounts move from kobo to whole naira (÷ 100, rounded half up)."""

from django.db import migrations, models


def to_naira(apps, schema_editor):
    Transaction = apps.get_model("escrow", "Transaction")
    for tx in Transaction.objects.all():
        tx.amount = (tx.amount_kobo + 50) // 100
        tx.payout = None if tx.payout_kobo is None else (tx.payout_kobo + 50) // 100
        tx.save(update_fields=["amount", "payout"])


class Migration(migrations.Migration):
    dependencies = [
        ("escrow", "0001_initial"),
    ]

    operations = [
        migrations.AddField(model_name="transaction", name="amount", field=models.PositiveIntegerField(null=True)),
        migrations.AddField(
            model_name="transaction", name="payout", field=models.PositiveIntegerField(blank=True, null=True)
        ),
        migrations.RunPython(to_naira, migrations.RunPython.noop),
        migrations.RemoveField(model_name="transaction", name="amount_kobo"),
        migrations.RemoveField(model_name="transaction", name="payout_kobo"),
        migrations.AlterField(model_name="transaction", name="amount", field=models.PositiveIntegerField()),
    ]
