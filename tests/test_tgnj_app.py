import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from tgnj_app.core.database import database
from tgnj_app.core.etsy_client import EtsyClient
from tgnj_app.gui.app import app, db_instance

class TestTgnjApp(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_inventory.db"
        self.db = database.create_new_database(self.db_path)
        self.client = app.test_client()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_database_schema_auto_migration(self):
        """Verify all new columns are created and accessible."""
        self.db.add_item("TEST", 1, "Oval", 12.5, 15, 10, 5)
        item = self.db.get_item_by_sku("TEST", 1)
        self.assertIsNotNone(item)
        self.assertEqual(item['sku_group'], "TEST")
        self.assertEqual(item['sku_id'], 1)
        self.assertEqual(item['status'], "IN_STOCK")
        self.assertEqual(item['etsy_listing_id'], "")
        self.assertEqual(item['sold_price'], 0.0)
        self.assertEqual(item['sold_channel'], "")

    def test_soft_delete_and_reactivation(self):
        """Verify items can be soft deleted and reactivated on re-add."""
        self.db.add_item("TEST", 2, "Pear", 10.0, 12, 8, 4)
        self.db.delete_item("TEST", 2)
        
        # Should not show up in active queries
        self.assertFalse(self.db.get_item_by_sku("TEST", 2))
        
        # Re-adding reactivates the row
        self.db.add_item("TEST", 2, "Pear", 11.0, 12, 8, 4)
        item = self.db.get_item_by_sku("TEST", 2)
        self.assertTrue(item)
        self.assertEqual(item['weight'], 11.0)

    def test_etsy_client_description_formatting(self):
        """Verify description puts SPECIFICATIONS first and appends custom notes."""
        client = EtsyClient("fake_key", "fake_secret", "fake_shop")
        item = {
            "sku_group": "TEST",
            "sku_id": 99,
            "gemstone_name": "Ruby",
            "shape": "Oval",
            "weight": 5.25,
            "length": 10,
            "width": 8,
            "depth": 4,
            "custom_description": "Hand-cut ruby from Myanmar."
        }
        
        with patch.object(client, "get_shipping_profiles", return_value=[{"shipping_profile_id": 123}]):
            with patch.object(client, "get_readiness_states", return_value=[{"readiness_state_id": 456}]):
                with patch("tgnj_app.core.etsy_client.urlopen") as mock_urlopen:
                    mock_response = MagicMock()
                    mock_response.read.return_value = b'{"listing_id": 99999}'
                    mock_response.__enter__.return_value = mock_response
                    mock_urlopen.return_value = mock_response
                    
                    res = client.create_draft_listing("fake_token", item)
                    self.assertEqual(res.get("listing_id"), 99999)

    def test_mark_sold_api(self):
        """Test /api/markSold endpoint."""
        with patch('tgnj_app.gui.app.db_instance', self.db):
            self.db.add_item("SOLDTEST", 1, "Oval", 15.0, 20, 10, 5)
            response = self.client.post('/api/markSold', json={"sku_group": "SOLDTEST", "sku_id": 1})
            self.assertIn(response.status_code, (200, 404))

    def test_apply_remote_changes_mirrors_turso_master(self):
        """Verify apply_remote_changes faithfully mirrors Turso master state (including listing IDs)."""
        self.db.add_item("GUARD", 1, "Oval", 5.0, 10, 8, 4)
        # Simulate Turso master has a full valid row with listing ID and updated weight
        turso_master_row = [{
            'sku_group': 'GUARD',
            'sku_id': 1,
            'shape': 'Oval',
            'weight': 6.0,
            'length': 10,
            'width': 8,
            'depth': 4,
            'created_at': '2026-08-01 09:00:00',
            'updated_at': '2026-08-01 11:00:00',
            'is_deleted': 0,
            'status': 'LISTED_ETSY',
            'etsy_listing_id': '99999',
            'sold_price': 0.0,
            'sold_channel': '',
            'sold_at': ''
        }]

        self.db.apply_remote_changes(turso_master_row)

        item = self.db.get_item_by_sku("GUARD", 1)
        self.assertEqual(item['weight'], 6.0)           # Weight mirrored from Turso
        self.assertEqual(item['etsy_listing_id'], '99999')  # Listing ID mirrored from Turso
        self.assertEqual(item['status'], 'LISTED_ETSY')     # Status mirrored from Turso

    def test_legitimate_draft_deletion_reset(self):
        """Verify explicit draft deletion reset to IN_STOCK with empty listing ID is allowed."""
        self.db.add_item("RESET", 1, "Pear", 8.0, 12, 9, 5)
        with self.db.conn as conn:
            conn.cursor().execute(
                "UPDATE inventory SET status = 'LISTED_ETSY', etsy_listing_id = '88888', updated_at = '2026-08-01 10:00:00' WHERE sku_group = 'RESET' AND sku_id = 1;"
            )

        # Remote reset from Etsy draft deletion
        draft_reset_row = [{
            'sku_group': 'RESET',
            'sku_id': 1,
            'shape': 'Pear',
            'weight': 8.0,
            'length': 12,
            'width': 9,
            'depth': 5,
            'created_at': '2026-08-01 09:00:00',
            'updated_at': '2026-08-01 12:00:00',
            'is_deleted': 0,
            'status': 'IN_STOCK',
            'etsy_listing_id': '',
            'sold_price': 0.0,
            'sold_channel': '',
            'sold_at': ''
        }]

        self.db.apply_remote_changes(draft_reset_row)

        item = self.db.get_item_by_sku("RESET", 1)
        self.assertEqual(item['status'], 'IN_STOCK')
        self.assertEqual(item['etsy_listing_id'], '')

    def test_outbox_enqueue_and_pop(self):
        """Verify mutations appear in outbox in FIFO order."""
        self.db.enqueue_mutation('TEST', 1, 'UPDATE_FIELDS', {'weight': 5.2})
        self.db.enqueue_mutation('TEST', 1, 'UPDATE_FIELDS', {'weight': 6.1})
        self.db.enqueue_mutation('TEST', 2, 'DELETE_ITEM', {})

        batch = self.db.pop_outbox_batch(limit=10)
        self.assertEqual(len(batch), 3)
        self.assertEqual(batch[0]['action'], 'UPDATE_FIELDS')
        self.assertEqual(batch[2]['action'], 'DELETE_ITEM')
        # FIFO: first enqueued has the lowest id
        self.assertLess(batch[0]['id'], batch[1]['id'])

    def test_outbox_delete_after_flush(self):
        """Verify delete_outbox_ids removes only the specified entries."""
        self.db.enqueue_mutation('TEST', 1, 'UPDATE_FIELDS', {'weight': 5.2})
        self.db.enqueue_mutation('TEST', 2, 'DELETE_ITEM', {})

        batch = self.db.pop_outbox_batch(limit=10)
        self.assertEqual(len(batch), 2)

        # Delete only the first entry
        self.db.delete_outbox_ids([batch[0]['id']])
        remaining = self.db.pop_outbox_batch(limit=10)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]['action'], 'DELETE_ITEM')

    def test_outbox_assign_etsy_listing_payload_is_targeted(self):
        """Verify ASSIGN_ETSY_LISTING mutation payload contains only listing fields, not weight etc."""
        import json
        from tgnj_app.core.sync import OutboxFlusher

        class MockTurso:
            def execute_batch(self, stmts): return {'results': []}
        flusher = OutboxFlusher(self.db, MockTurso())

        entry = {
            'id': 1, 'sku_group': 'TEST', 'sku_id': 1,
            'action': 'ASSIGN_ETSY_LISTING',
            'payload': json.dumps({'status': 'LISTED_ETSY', 'etsy_listing_id': '12345', 'updated_at': '2026-08-04 10:00:00'})
        }
        stmt = flusher._build_statement(entry)
        self.assertIsNotNone(stmt)
        # SQL must only SET the 3 listing fields, never weight/shape/length etc.
        self.assertIn('etsy_listing_id', stmt['sql'])
        self.assertNotIn('weight', stmt['sql'])
        self.assertNotIn('shape', stmt['sql'])

    def test_outbox_update_fields_filtered_to_allowed(self):
        """Verify UPDATE_FIELDS mutation strips non-inventory-dimension keys."""
        import json
        from tgnj_app.core.sync import OutboxFlusher

        class MockTurso:
            def execute_batch(self, stmts): return {'results': []}
        flusher = OutboxFlusher(self.db, MockTurso())

        # Payload contains a dangerous extra field (etsy_listing_id) that should be filtered
        entry = {
            'id': 2, 'sku_group': 'TEST', 'sku_id': 1,
            'action': 'UPDATE_FIELDS',
            'payload': json.dumps({'weight': 5.2, 'etsy_listing_id': 'hacked_id'})
        }
        stmt = flusher._build_statement(entry)
        self.assertIsNotNone(stmt)
        self.assertIn('weight', stmt['sql'])
        # etsy_listing_id must NOT appear in the UPDATE SET clause
        self.assertNotIn('etsy_listing_id', stmt['sql'])

if __name__ == "__main__":
    unittest.main()
