"""Database-level immutability for posted journals (GL-06).

The API already has no update or delete route for a posted journal. This trigger
makes the guarantee hold even for a raw SQL client, a data import or a future
endpoint that forgets the rule. Lines can be written only while their journal
is not posted.
"""

from __future__ import annotations

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION accounting_block_posted_journal_mutation()
RETURNS trigger AS $$
DECLARE
    parent_status text;
BEGIN
    IF TG_TABLE_NAME = 'accounting_journalentry' THEN
        IF TG_OP = 'UPDATE' AND OLD.status = 'posted' THEN
            RAISE EXCEPTION 'A posted journal entry is immutable';
        END IF;
        IF TG_OP = 'DELETE' AND OLD.status = 'posted' THEN
            RAISE EXCEPTION 'A posted journal entry cannot be deleted';
        END IF;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT' THEN
        SELECT status INTO parent_status
        FROM accounting_journalentry WHERE id = NEW.journal_id;
        IF parent_status = 'posted' THEN
            RAISE EXCEPTION 'Lines cannot be added to a posted journal entry';
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        SELECT status INTO parent_status
        FROM accounting_journalentry WHERE id = OLD.journal_id;
        IF parent_status = 'posted' OR OLD.journal_id <> NEW.journal_id THEN
            RAISE EXCEPTION 'Lines of a posted journal entry are immutable';
        END IF;
        RETURN NEW;
    ELSE
        SELECT status INTO parent_status
        FROM accounting_journalentry WHERE id = OLD.journal_id;
        IF parent_status = 'posted' THEN
            RAISE EXCEPTION 'Lines of a posted journal entry cannot be deleted';
        END IF;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER accounting_journalentry_immutable
BEFORE UPDATE OR DELETE ON accounting_journalentry
FOR EACH ROW EXECUTE FUNCTION accounting_block_posted_journal_mutation();

CREATE TRIGGER accounting_journalline_immutable
BEFORE INSERT OR UPDATE OR DELETE ON accounting_journalline
FOR EACH ROW EXECUTE FUNCTION accounting_block_posted_journal_mutation();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS accounting_journalline_immutable ON accounting_journalline;
DROP TRIGGER IF EXISTS accounting_journalentry_immutable ON accounting_journalentry;
DROP FUNCTION IF EXISTS accounting_block_posted_journal_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [("accounting", "0001_initial")]

    operations = [
        migrations.RunSQL(FORWARD, BACKWARD),
    ]
