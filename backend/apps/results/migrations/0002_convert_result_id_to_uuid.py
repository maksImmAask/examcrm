
import uuid

from django.db import migrations, models


def populate_uuid_ids(apps, schema_editor):
    ExamResult = apps.get_model("results", "ExamResult")

    for result in ExamResult.objects.all().iterator():
        result.uuid_id = uuid.uuid4()
        result.save(update_fields=["uuid_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("results", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="examresult",
            name="uuid_id",
            field=models.UUIDField(
                null=True,
                editable=False,
            ),
        ),
        migrations.RunPython(
            populate_uuid_ids,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="examresult",
            name="id",
        ),
        migrations.RenameField(
            model_name="examresult",
            old_name="uuid_id",
            new_name="id",
        ),
        migrations.AlterField(
            model_name="examresult",
            name="id",
            field=models.UUIDField(
                primary_key=True,
                default=uuid.uuid4,
                editable=False,
                serialize=False,
            ),
        ),
    ]
