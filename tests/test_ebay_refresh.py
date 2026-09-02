import unittest
from tgnj_app.core.ebay_refresh import (
    parse_active_listings_csv,
    parse_quality_report_xlsx,
    extract_sku_group_prefix,
    analyze_sku_groups,
    triage_sku_group,
    generate_action_end_csv
)

class TestEbayRefresh(unittest.TestCase):
    
    def test_extract_sku_group_prefix(self):
        self.assertEqual(extract_sku_group_prefix("PP01-38"), "PP01")
        self.assertEqual(extract_sku_group_prefix("FS01_10"), "FS01")
        self.assertEqual(extract_sku_group_prefix("BT-_10"), "BT")
        self.assertEqual(extract_sku_group_prefix("A1-018"), "A1")
        self.assertEqual(extract_sku_group_prefix("  j1-002  "), "J1")
        
    def test_parse_active_listings_csv(self):
        sample_csv = (
            '"Item number","Title","Variation details","Custom label (SKU)","Available quantity","Format","Currency","Start price","Auction Buy It Now price","Reserve price","Current price","Sold quantity","Watchers","Bids","Start date"\n'
            '"375916413265","Natural Blue Pietersite Oval Cabochon","","PP01-38","1","FIXED_PRICE","USD","36.78","","","36.78","0","4","","Jan-10-25"\n'
            '"375916413266","Natural Blue Pietersite Cushion Cabochon","","PP01-45","1","FIXED_PRICE","USD","29.88","","","29.88","0","0","","Jan-10-25"\n'
        )
        listings = parse_active_listings_csv(sample_csv)
        self.assertEqual(len(listings), 2)
        self.assertEqual(listings[0]["item_id"], "375916413265")
        self.assertEqual(listings[0]["sku_group"], "PP01")
        self.assertEqual(listings[0]["watchers"], 4)
        self.assertEqual(listings[1]["watchers"], 0)

    def test_analyze_and_triage_sku_groups(self):
        sample_listings = [
            {"item_id": "101", "custom_label": "A3-01", "sku_group": "A3", "watchers": 0, "sold_qty": 0, "daily_impressions": 1.0, "item_age_days": 400},
            {"item_id": "102", "custom_label": "A3-02", "sku_group": "A3", "watchers": 0, "sold_qty": 0, "daily_impressions": 0.5, "item_age_days": 410},
            {"item_id": "201", "custom_label": "PP01-01", "sku_group": "PP01", "watchers": 5, "sold_qty": 0, "daily_impressions": 15.0, "item_age_days": 500},
            {"item_id": "202", "custom_label": "PP01-02", "sku_group": "PP01", "watchers": 0, "sold_qty": 0, "daily_impressions": 1.0, "item_age_days": 600},
            {"item_id": "203", "custom_label": "PP01-03", "sku_group": "PP01", "watchers": 0, "sold_qty": 1, "daily_impressions": 2.0, "item_age_days": 300},
        ]
        
        summaries = analyze_sku_groups(sample_listings, age_threshold=90)
        self.assertEqual(len(summaries), 2)
        
        # A3 has 100% stale items, so its urgency score should be highest
        top_group = summaries[0]
        self.assertEqual(top_group["sku_group"], "A3")
        self.assertEqual(top_group["stale_percentage"], 100.0)
        
        # Triage PP01
        triage_pp01 = triage_sku_group(sample_listings, "PP01", age_threshold=90, watcher_threshold=2)
        self.assertEqual(len(triage_pp01["protected"]), 2) # PP01-01 (watchers=5) and PP01-03 (sales=1)
        self.assertEqual(len(triage_pp01["stale"]), 1)     # PP01-02 (watchers=0, sales=0, age=600)
        self.assertEqual(len(triage_pp01["evergreen"]), 1) # PP01-03 (sales=1)

    def test_generate_action_end_csv(self):
        stale_items = [
            {"item_id": "375916413266", "custom_label": "PP01-45"},
            {"item_id": "375916413267", "custom_label": "PP01-46"},
        ]
        csv_out = generate_action_end_csv(stale_items, end_code="NotAvailable")
        lines = [line.strip() for line in csv_out.strip().splitlines()]
        self.assertEqual(lines[0], "Action,Item number,EndCode")
        self.assertEqual(lines[1], "End,375916413266,NotAvailable")
        self.assertEqual(lines[2], "End,375916413267,NotAvailable")

    def test_flask_ebay_routes(self):
        from tgnj_app.gui.app import app
        client = app.test_client()
        
        # GET /ebay page
        res = client.get('/ebay')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'TakshGems eBay Operations Hub', res.data)
        
        # POST /api/ebay/export-action-end
        res = client.post('/api/ebay/export-action-end', json={
            'stale_items': [{'item_id': '112233445566'}]
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Action,Item number,EndCode', res.data)
        self.assertIn(b'End,112233445566,NotAvailable', res.data)

if __name__ == "__main__":
    unittest.main()
