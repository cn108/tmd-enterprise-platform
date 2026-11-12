from __future__ import annotations

from django.db import migrations


FORWARD = """
CREATE OR REPLACE FUNCTION inventory_stock_movement_immutable()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'stock movements are append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER inventory_stock_movement_no_update
BEFORE UPDATE OR DELETE ON inventory_stockmovement
FOR EACH ROW EXECUTE FUNCTION inventory_stock_movement_immutable();
"""

REVERSE = """
DROP TRIGGER IF EXISTS inventory_stock_movement_no_update ON inventory_stockmovement;
DROP FUNCTION IF EXISTS inventory_stock_movement_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [("inventory", "0002_alter_inventorypolicy_valuation_method")]

    operations = [migrations.RunSQL(FORWARD, REVERSE)]
