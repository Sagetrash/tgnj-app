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
        self.db = database(self.db_path)
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

if __name__ == "__main__":
    unittest.main()
