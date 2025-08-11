from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0002_alter_class_curriculum"),
    ]

    operations = [
        # Update Django's *state* to include the field
        migrations.AddField(
            model_name="class",
            name="curriculum",
            field=models.ForeignKey(
                to="dashboard.curriculum",
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="classes",
            ),
        ),
        # Ensure the DB column/constraint exist even if history drifted
        migrations.RunSQL(
            sql=[
                # Add column if missing
                (
                    'ALTER TABLE "dashboard_class" '
                    'ADD COLUMN IF NOT EXISTS "curriculum_id" bigint NULL;'
                ),
                # Create FK if missing
                (
                    'DO $$ BEGIN '
                    'IF NOT EXISTS ('
                    '  SELECT 1 FROM information_schema.table_constraints '
                    "  WHERE constraint_name = 'dashboard_class_curriculum_id_d20d78f6_fk_dashboard'"
                    ') THEN '
                    'ALTER TABLE "dashboard_class" '
                    'ADD CONSTRAINT "dashboard_class_curriculum_id_d20d78f6_fk_dashboard" '
                    'FOREIGN KEY ("curriculum_id") '
                    'REFERENCES "dashboard_curriculum" ("id") '
                    'DEFERRABLE INITIALLY DEFERRED; '
                    'END IF; '
                    'END $$;'
                ),
                # Index if missing
                (
                    'CREATE INDEX IF NOT EXISTS "dashboard_class_curriculum_id_d20d78f6" '
                    'ON "dashboard_class" ("curriculum_id");'
                ),
            ],
            reverse_sql=[
                # Safe reverse: drop FK/index if they exist; keep column (or drop if you want)
                (
                    'DO $$ BEGIN '
                    'IF EXISTS ('
                    "  SELECT 1 FROM information_schema.table_constraints "
                    "  WHERE constraint_name = 'dashboard_class_curriculum_id_d20d78f6_fk_dashboard'"
                    ') THEN '
                    'ALTER TABLE "dashboard_class" '
                    'DROP CONSTRAINT "dashboard_class_curriculum_id_d20d78f6_fk_dashboard"; '
                    'END IF; '
                    'END $$;'
                ),
                (
                    'DROP INDEX IF EXISTS "dashboard_class_curriculum_id_d20d78f6";'
                ),
                # (Optional) drop column on reverse:
                # 'ALTER TABLE "dashboard_class" DROP COLUMN IF EXISTS "curriculum_id";'
            ],
        ),
    ]