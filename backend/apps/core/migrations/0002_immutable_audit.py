from __future__ import annotations

from django.db import migrations


FORWARD = """
CREATE OR REPLACE FUNCTION core_audit_event_immutable()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit events are append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER core_audit_event_no_update
BEFORE UPDATE OR DELETE ON core_auditevent
FOR EACH ROW EXECUTE FUNCTION core_audit_event_immutable();
"""

REVERSE = """
DROP TRIGGER IF EXISTS core_audit_event_no_update ON core_auditevent;
DROP FUNCTION IF EXISTS core_audit_event_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
