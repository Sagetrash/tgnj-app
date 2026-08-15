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

    def test_sync_deleted_etsy_drafts_connection_safety_guard(self):
        """Verify sync_deleted_etsy_drafts NEVER resets listings if API returns empty live_ids or 401 error."""
        from tgnj_app.gui.app import sync_deleted_etsy_drafts

        self.db.add_item("SAFE", 1, "Pear", 10.0, 12, 8, 4)
        with self.db.conn as conn:
            conn.cursor().execute(
                "UPDATE inventory SET status = 'LISTED_ETSY', etsy_listing_id = '77777', updated_at = '2026-08-01 10:00:00' WHERE sku_group = 'SAFE' AND sku_id = 1;"
            )

        # Mock EtsyClient returning empty results (e.g. 401 Unauthorized or disconnected)
        mock_client = MagicMock()
        mock_client.get_shop_listings_by_state.return_value = {"error": "invalid_token", "results": []}

        with patch('tgnj_app.gui.app.db_instance', self.db):
            reset_count = sync_deleted_etsy_drafts(mock_client, "fake_token")
            self.assertEqual(reset_count, 0)  # Safety guard triggered!

        # Item remains LISTED_ETSY with listing_id = 77777 (not wiped!)
        item = self.db.get_item_by_sku("SAFE", 1)
        self.assertEqual(item['status'], 'LISTED_ETSY')
        self.assertEqual(item['etsy_listing_id'], '77777')

    def test_etsy_client_get_all_shop_listings_by_state_pagination(self):
        """Verify get_all_shop_listings_by_state paginates until all items across pages are returned."""
        client = EtsyClient("fake_key", "fake_secret", "fake_shop")

        def mock_get_listings(access_token, state="active", limit=100, offset=0):
            if offset == 0:
                # Page 1 returns 100 items
                return {"count": 125, "results": [{"listing_id": i} for i in range(100)]}
            elif offset == 100:
                # Page 2 returns remaining 25 items
                return {"count": 125, "results": [{"listing_id": i} for i in range(100, 125)]}
            return {"count": 125, "results": []}

        with patch.object(client, "get_shop_listings_by_state", side_effect=mock_get_listings):
            all_items = client.get_all_shop_listings_by_state("fake_token", state="draft")
            self.assertEqual(len(all_items), 125)
            self.assertEqual(all_items[0]["listing_id"], 0)
            self.assertEqual(all_items[124]["listing_id"], 124)

    def test_etsy_client_deactivate_listing_payload(self):
        """Verify deactivate_listing sends PATCH state=inactive request."""
        client = EtsyClient("fake_key", "fake_secret", "fake_shop")
        with patch("tgnj_app.core.etsy_client.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"state": "inactive"}'
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            res = client.deactivate_listing("fake_token", "12345")
            self.assertEqual(res.get("state"), "inactive")
            
            # Check URL and method in request
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.get_method(), "PATCH")
            self.assertIn("/v3/application/shops/fake_shop/listings/12345", req.full_url)

    def test_mark_sold_auto_deactivates_etsy_listing(self):
        """Verify markSold endpoint deactivates Etsy listing if item was listed."""
        self.db.add_item("TEST", 5, "Emerald", 2.5, 8, 6, 4)
        with self.db.conn as conn:
            conn.cursor().execute(
                "UPDATE inventory SET status = 'LISTED_ETSY', etsy_listing_id = '998877' WHERE sku_group = 'TEST' AND sku_id = 5;"
            )

        with patch('tgnj_app.gui.app.db_instance', self.db), \
             patch('tgnj_app.gui.app.get_fresh_etsy_tokens', return_value=('key', 'sec', 'shop', 'tok', 'ref')), \
             patch('tgnj_app.core.etsy_client.EtsyClient.deactivate_listing', return_value={'state': 'inactive'}) as mock_deactivate:
            
            response = self.client.post('/api/markSold/TEST/5', json={'price': 150.0, 'channel': 'Instagram'})
            self.assertEqual(response.status_code, 200)
            self.assertIn("deactivated live Etsy Listing #998877", response.json['message'])
            mock_deactivate.assert_called_once_with('tok', '998877')

        # Item status updated to SOLD in database
        item = self.db.get_item_by_sku("TEST", 5)
        self.assertEqual(item['status'], 'SOLD')

    def test_mark_sold_deletes_etsy_draft_listing(self):
        """Verify markSold endpoint deletes Etsy draft listing if status was DRAFT_ETSY."""
        self.db.add_item("TEST", 7, "Topaz", 1.5, 6, 4, 3)
        with self.db.conn as conn:
            conn.cursor().execute(
                "UPDATE inventory SET status = 'DRAFT_ETSY', etsy_listing_id = '112233' WHERE sku_group = 'TEST' AND sku_id = 7;"
            )

        with patch('tgnj_app.gui.app.db_instance', self.db), \
             patch('tgnj_app.gui.app.get_fresh_etsy_tokens', return_value=('key', 'sec', 'shop', 'tok', 'ref')), \
             patch('tgnj_app.core.etsy_client.EtsyClient.update_listing_title', return_value={'title': 'delete'}) as mock_update:
            
            response = self.client.post('/api/markSold/TEST/7', json={'price': 40.0, 'channel': 'Offline'})
            self.assertEqual(response.status_code, 200)
            self.assertIn("renamed Etsy Draft Listing to 'delete' #112233", response.json['message'])
            mock_update.assert_called_once_with('tok', '112233', 'delete')

        item = self.db.get_item_by_sku("TEST", 7)
        self.assertEqual(item['status'], 'SOLD')

    def test_etsy_client_delete_listing_payload(self):
        """Verify delete_listing sends DELETE request to Etsy OpenAPI."""
        client = EtsyClient("fake_key", "fake_secret", "fake_shop")
        with patch("tgnj_app.core.etsy_client.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 204
            mock_resp.read.return_value = b''
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            res = client.delete_listing("fake_token", "112233")
            self.assertTrue(res.get("success"))
            
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.get_method(), "DELETE")
            self.assertIn("/v3/application/listings/112233", req.full_url)


    def test_etsy_client_reactivate_listing_payload(self):
        """Verify reactivate_listing sends PATCH state=active request."""
        client = EtsyClient("fake_key", "fake_secret", "fake_shop")
        with patch("tgnj_app.core.etsy_client.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"state": "active"}'
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            res = client.reactivate_listing("fake_token", "12345")
            self.assertEqual(res.get("state"), "active")
            
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.get_method(), "PATCH")
            self.assertIn("/v3/application/shops/fake_shop/listings/12345", req.full_url)

    def test_restore_item_auto_reactivates_etsy_listing(self):
        """Verify restoreItem endpoint reactivates Etsy listing if item has listing_id."""
        self.db.add_item("TEST", 6, "Sapphire", 4.0, 10, 8, 5)
        with self.db.conn as conn:
            conn.cursor().execute(
                "UPDATE inventory SET status = 'SOLD', sold_price = 200.0, etsy_listing_id = '554433' WHERE sku_group = 'TEST' AND sku_id = 6;"
            )

        with patch('tgnj_app.gui.app.db_instance', self.db), \
             patch('tgnj_app.gui.app.get_fresh_etsy_tokens', return_value=('key', 'sec', 'shop', 'tok', 'ref')), \
             patch('tgnj_app.core.etsy_client.EtsyClient.reactivate_listing', return_value={'state': 'active'}) as mock_reactivate:
            
            response = self.client.post('/api/restoreItem/TEST/6')
            self.assertEqual(response.status_code, 200)
            self.assertIn("reactivated Etsy Listing #554433", response.json['message'])
            mock_reactivate.assert_called_once_with('tok', '554433')

        item = self.db.get_item_by_sku("TEST", 6)
        self.assertEqual(item['status'], 'LISTED_ETSY')
        self.assertEqual(item['sold_price'], 0.0)

    def test_deactivate_listing_http_error_handling(self):
        """Verify deactivate_listing catches HTTP errors (401/404) gracefully."""
        from urllib.error import HTTPError
        client = EtsyClient("fake_key", "fake_secret", "fake_shop")
        
        # Test HTTP 401
        err_401 = HTTPError("url", 401, "Unauthorized", {}, None)
        with patch("tgnj_app.core.etsy_client.urlopen", side_effect=err_401):
            res = client.deactivate_listing("fake_token", "12345")
            self.assertIn("error", res)
            self.assertEqual(res.get("code"), 401)

        # Test HTTP 404
        err_404 = HTTPError("url", 404, "Not Found", {}, None)
        with patch("tgnj_app.core.etsy_client.urlopen", side_effect=err_404):
            res = client.deactivate_listing("fake_token", "99999")
            self.assertIn("error", res)
            self.assertEqual(res.get("code"), 404)

    def test_deactivate_listing_network_exception(self):
        """Verify deactivate_listing catches network offline / socket timeout exceptions."""
        client = EtsyClient("fake_key", "fake_secret", "fake_shop")
        with patch("tgnj_app.core.etsy_client.urlopen", side_effect=Exception("Connection timed out")):
            res = client.deactivate_listing("fake_token", "12345")
            self.assertIn("error", res)
            self.assertEqual(res.get("error"), "Connection timed out")

    def test_reactivate_listing_http_error_handling(self):
        """Verify reactivate_listing catches HTTP errors (401/404) gracefully."""
        from urllib.error import HTTPError
        client = EtsyClient("fake_key", "fake_secret", "fake_shop")
        
        err_401 = HTTPError("url", 401, "Unauthorized", {}, None)
        with patch("tgnj_app.core.etsy_client.urlopen", side_effect=err_401):
            res = client.reactivate_listing("fake_token", "12345")
            self.assertIn("error", res)
            self.assertEqual(res.get("code"), 401)

    def test_reactivate_listing_network_exception(self):
        """Verify reactivate_listing catches network timeout exceptions."""
        client = EtsyClient("fake_key", "fake_secret", "fake_shop")
        with patch("tgnj_app.core.etsy_client.urlopen", side_effect=Exception("Network unreachable")):
            res = client.reactivate_listing("fake_token", "12345")
            self.assertIn("error", res)
            self.assertEqual(res.get("error"), "Network unreachable")

    def test_mark_sold_non_existent_item_returns_404(self):
        """Verify markSold returns 404 when item doesn't exist."""
        with patch('tgnj_app.gui.app.db_instance', self.db):
            response = self.client.post('/api/markSold/NONEXISTENT/999', json={})
            self.assertEqual(response.status_code, 404)
            self.assertIn("Item not found", response.json['message'])

    def test_mark_sold_succeeds_locally_even_if_etsy_api_fails(self):
        """Verify markSold updates local database to SOLD even if Etsy API returns an error or fails."""
        self.db.add_item("FAILTEST", 1, "Ruby", 3.0, 9, 7, 4)
        with self.db.conn as conn:
            conn.cursor().execute(
                "UPDATE inventory SET status = 'LISTED_ETSY', etsy_listing_id = '887766' WHERE sku_group = 'FAILTEST' AND sku_id = 1;"
            )

        with patch('tgnj_app.gui.app.db_instance', self.db), \
             patch('tgnj_app.gui.app.get_fresh_etsy_tokens', return_value=('key', 'sec', 'shop', 'tok', 'ref')), \
             patch('tgnj_app.core.etsy_client.EtsyClient.deactivate_listing', return_value={'error': 'HTTP 401 Unauthorized', 'code': 401}):
            
            response = self.client.post('/api/markSold/FAILTEST/1', json={'price': 80.0, 'channel': 'Offline'})
            # Must STILL succeed locally!
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("deactivated Etsy Listing", response.json['message'])

        # Database is updated locally to SOLD
        item = self.db.get_item_by_sku("FAILTEST", 1)
        self.assertEqual(item['status'], 'SOLD')
        self.assertEqual(item['sold_price'], 80.0)

    def test_restore_item_non_existent_item_returns_404(self):
        """Verify restoreItem returns 404 when item doesn't exist."""
        with patch('tgnj_app.gui.app.db_instance', self.db):
            response = self.client.post('/api/restoreItem/NONEXISTENT/999')
            self.assertEqual(response.status_code, 404)

    def test_restore_item_succeeds_locally_even_if_etsy_api_fails(self):
        """Verify restoreItem updates local status even if Etsy reactivation API fails."""
        self.db.add_item("FAILTEST", 2, "Garnet", 5.0, 11, 9, 6)
        with self.db.conn as conn:
            conn.cursor().execute(
                "UPDATE inventory SET status = 'SOLD', etsy_listing_id = '556677' WHERE sku_group = 'FAILTEST' AND sku_id = 2;"
            )

        with patch('tgnj_app.gui.app.db_instance', self.db), \
             patch('tgnj_app.gui.app.get_fresh_etsy_tokens', return_value=('key', 'sec', 'shop', 'tok', 'ref')), \
             patch('tgnj_app.core.etsy_client.EtsyClient.reactivate_listing', return_value={'error': 'Connection timed out'}):
            
            response = self.client.post('/api/restoreItem/FAILTEST/2')
            # Must STILL succeed locally!
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("reactivated Etsy Listing", response.json['message'])

        item = self.db.get_item_by_sku("FAILTEST", 2)
        self.assertEqual(item['status'], 'LISTED_ETSY')
        self.assertEqual(item['sold_price'], 0.0)

if __name__ == "__main__":
    unittest.main()




