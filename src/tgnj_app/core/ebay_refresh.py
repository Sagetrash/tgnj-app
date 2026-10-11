import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import List, Dict, Any, Tuple

def parse_active_listings_csv(csv_content: str) -> List[Dict[str, Any]]:
    """
    Parses eBay Active Listings CSV (eBay-all-active-listings-report-*.csv).
    Returns list of normalized listing dicts.
    """
    csv_content = csv_content.lstrip('\ufeff')
    reader = csv.DictReader(io.StringIO(csv_content))
    listings = []
    
    for row in reader:
        item_id = (row.get("Item number") or row.get("Item Id") or "").strip().replace('"', '')
        custom_label = (row.get("Custom label (SKU)") or row.get("Custom label") or "").strip()
        if not item_id or not custom_label:
            continue
            
        title = (row.get("Title") or row.get("Item title") or "").strip()
        variation = (row.get("Variation details") or "").strip()
        
        try:
            watchers = int(float(row.get("Watchers") or row.get("Number of watchers") or 0))
        except (ValueError, TypeError):
            watchers = 0
            
        try:
            sold_qty = int(float(row.get("Sold quantity") or row.get("Sales count in last 31 days") or 0))
        except (ValueError, TypeError):
            sold_qty = 0
            
        try:
            price = float(row.get("Current price") or row.get("Start price") or row.get("Price") or 0.0)
        except (ValueError, TypeError):
            price = 0.0
            
        # Parse SKU group prefix
        sku_group = extract_sku_group_prefix(custom_label)
        
        listings.append({
            "item_id": item_id,
            "custom_label": custom_label,
            "sku_group": sku_group,
            "title": title,
            "variation": variation,
            "watchers": watchers,
            "sold_qty": sold_qty,
            "price": price,
            "daily_impressions": 0.0,
            "ctr": "No clicks" if watchers == 0 else "Active",
            "item_age_days": 0,
            "is_variation": bool(variation and not custom_label.endswith("_10")) # multi-variation marker
        })
        
    return listings


def parse_quality_report_xlsx(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses eBay Listing Quality Report (.xlsx) directly from disk using stdlib zipfile/xml.
    Extracts itemized listing metrics from 'Loose Gemstones' sheet (or first listing sheet).
    """
    listings = []
    with zipfile.ZipFile(file_path, 'r') as z:
        wb_tree = ET.fromstring(z.read('xl/workbook.xml'))
        rel_tree = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rels = {r.get('Id'): r.get('Target') for r in rel_tree}
        
        ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        r_ns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
        
        sheet_files = {}
        for s in wb_tree.findall(f'{ns}sheets/{ns}sheet'):
            r_id = s.get(f'{r_ns}id')
            sheet_files[s.get('name')] = 'xl/' + rels[r_id]

        # Shared strings lookup table
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            ss_tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in ss_tree.findall(f'{ns}si'):
                t = si.find(f'{ns}t')
                if t is not None and t.text is not None:
                    shared_strings.append(t.text)
                else:
                    parts = [r.find(f'{ns}t').text for r in si.findall(f'{ns}r') if r.find(f'{ns}t') is not None and r.find(f'{ns}t').text is not None]
                    shared_strings.append(''.join(parts))

        # Target sheet priority: Loose Gemstones or any sheet with rows > 50
        target_sheet_file = sheet_files.get('Loose Gemstones')
        if not target_sheet_file:
            for s_name, s_file in sheet_files.items():
                if s_name not in ('Summary', 'Guide', 'Google Shopping Rejections'):
                    target_sheet_file = s_file
                    break
                    
        if not target_sheet_file:
            return listings

        s_tree = ET.fromstring(z.read(target_sheet_file))
        rows = s_tree.findall(f'{ns}sheetData/{ns}row')
        
        # Locate header row (Row containing "Item Id" or "Custom label")
        header_map = {}
        header_row_idx = -1
        
        for idx, r in enumerate(rows[:60]):
            cols = {}
            for c in r.findall(f'{ns}c'):
                col_name = ''.join([ch for ch in c.get('r') if ch.isalpha()])
                val = get_cell_value(c, ns, shared_strings)
                cols[val.strip()] = col_name
            if 'Item Id' in cols or 'Custom label' in cols:
                header_map = cols
                header_row_idx = idx
                break
                
        if header_row_idx == -1:
            return listings
            
        item_id_col = header_map.get('Item Id', 'AD')
        sku_col = header_map.get('Custom label', 'AM')
        title_col = header_map.get('Item title', 'B')
        age_col = header_map.get('Item age in days', 'AK')
        impressions_col = header_map.get('Daily impressions per listing', 'F')
        ctr_col = header_map.get('Click-through rate', 'G')
        sales_col = header_map.get('Sales count in last 31 days', 'AL')
        watchers_col = header_map.get('Number of watchers', 'AN')
        price_col = header_map.get('Price', 'AE')
        
        for r in rows[header_row_idx + 1:]:
            row_vals = {}
            for c in r.findall(f'{ns}c'):
                col_name = ''.join([ch for ch in c.get('r') if ch.isalpha()])
                row_vals[col_name] = get_cell_value(c, ns, shared_strings)
                
            item_id = row_vals.get(item_id_col, '').strip()
            custom_label = row_vals.get(sku_col, '').strip()
            
            if not item_id or not custom_label:
                continue
                
            sku_group = extract_sku_group_prefix(custom_label)
            title = row_vals.get(title_col, '').strip()
            
            try:
                age = int(float(row_vals.get(age_col, 0)))
            except (ValueError, TypeError):
                age = 0
                
            try:
                impressions = float(row_vals.get(impressions_col, 0.0))
            except (ValueError, TypeError):
                impressions = 0.0
                
            ctr = row_vals.get(ctr_col, '').strip()
            
            try:
                sales = int(float(row_vals.get(sales_col, 0)))
            except (ValueError, TypeError):
                sales = 0
                
            try:
                watchers = int(float(row_vals.get(watchers_col, 0)))
            except (ValueError, TypeError):
                watchers = 0
                
            try:
                price = float(row_vals.get(price_col, 0.0))
            except (ValueError, TypeError):
                price = 0.0

            listings.append({
                "item_id": item_id,
                "custom_label": custom_label,
                "sku_group": sku_group,
                "title": title,
                "watchers": watchers,
                "sold_qty": sales,
                "price": price,
                "daily_impressions": impressions,
                "ctr": ctr,
                "item_age_days": age,
                "is_variation": False
            })
            
    return listings


def extract_sku_group_prefix(custom_label: str) -> str:
    """
    Extracts the clean SKU Group prefix from a custom label string.
    Examples:
        'PP01-38' -> 'PP01'
        'FS01_10' -> 'FS01'
        'BT-_10'  -> 'BT'
        'A1-018'  -> 'A1'
    """
    label = custom_label.strip().upper()
    parts = re.split(r'[-_]', label)
    prefix = parts[0].strip()
    return prefix if prefix else "OTHER"


def get_cell_value(c: ET.Element, ns: str, shared_strings: List[str]) -> str:
    """Helper to decode cell value from XLSX XML element."""
    v = c.find(f'{ns}v')
    t = c.get('t')
    if v is not None and v.text is not None:
        val = v.text
        if t == 's' and val.isdigit() and int(val) < len(shared_strings):
            return shared_strings[int(val)]
        return val
    return ""


def analyze_sku_groups(listings: List[Dict[str, Any]], age_threshold: int = 90) -> List[Dict[str, Any]]:
    """
    Aggregates listings by SKU group prefix and ranks groups by Refresh Urgency.
    Returns list of group summary dicts sorted by urgency_score DESC.
    """
    groups = defaultdict(lambda: {
        "sku_group": "",
        "total_count": 0,
        "stale_count": 0,
        "protected_count": 0,
        "evergreen_count": 0,
        "total_age": 0,
        "total_watchers": 0,
        "total_impressions": 0.0,
        "sample_title": ""
    })
    
    for item in listings:
        grp = item["sku_group"]
        g = groups[grp]
        g["sku_group"] = grp
        g["total_count"] += 1
        g["total_age"] += item.get("item_age_days", 0)
        g["total_watchers"] += item.get("watchers", 0)
        g["total_impressions"] += item.get("daily_impressions", 0.0)
        
        if not g["sample_title"]:
            g["sample_title"] = item.get("title", "")
            
        watchers = item.get("watchers", 0)
        sales = item.get("sold_qty", 0)
        impressions = item.get("daily_impressions", 0.0)
        age = item.get("item_age_days", 0)
        
        is_winner = watchers >= 2 or sales > 0 or impressions >= 10.0
        is_evergreen = sales > 0
        is_stale = (not is_winner) and (age >= age_threshold or age == 0)
        
        if is_evergreen:
            g["evergreen_count"] += 1
        if is_winner:
            g["protected_count"] += 1
        elif is_stale:
            g["stale_count"] += 1

    summary_list = []
    for grp, data in groups.items():
        total = data["total_count"]
        stale = data["stale_count"]
        avg_age = round(data["total_age"] / total) if total > 0 else 0
        stale_pct = round((stale / total) * 100, 1) if total > 0 else 0.0
        
        urgency_score = round(stale_pct * avg_age, 1)
        
        summary_list.append({
            "sku_group": grp,
            "total_count": total,
            "stale_count": stale,
            "protected_count": data["protected_count"],
            "evergreen_count": data["evergreen_count"],
            "avg_age_days": avg_age,
            "stale_percentage": stale_pct,
            "urgency_score": urgency_score,
            "sample_title": data["sample_title"]
        })
        
    summary_list.sort(key=lambda x: x["urgency_score"], reverse=True)
    return summary_list


def triage_sku_group(listings: List[Dict[str, Any]], group_prefix: str, age_threshold: int = 90, watcher_threshold: int = 2) -> Dict[str, List[Dict[str, Any]]]:
    """
    Triages listings for a specific SKU group into 3 operational buckets:
    - protected: Winners (keep active)
    - evergreen: Recyclable slots with sales history
    - stale: Candidates for Action=End
    """
    protected = []
    evergreen = []
    stale = []
    
    group_prefix = group_prefix.strip().upper()
    
    for item in listings:
        if item["sku_group"] != group_prefix:
            continue
            
        watchers = item.get("watchers", 0)
        sales = item.get("sold_qty", 0)
        impressions = item.get("daily_impressions", 0.0)
        age = item.get("item_age_days", 0)
        
        is_winner = watchers >= watcher_threshold or sales > 0 or impressions >= 10.0
        
        if sales > 0:
            evergreen.append(item)
            protected.append(item)
        elif is_winner:
            protected.append(item)
        elif age >= age_threshold or age == 0:
            stale.append(item)
        else:
            protected.append(item)
            
    return {
        "protected": protected,
        "evergreen": evergreen,
        "stale": stale
    }


def generate_action_end_csv(stale_items: List[Dict[str, Any]], end_code: str = "NotAvailable") -> str:
    """
    Generates official eBay Seller Hub Reports compliant CSV for bulk ending listings.
    Output headers: Action,Item number,EndCode
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Action", "Item number", "EndCode"])
    
    seen_ids = set()
    for item in stale_items:
        item_id = str(item.get("item_id") or item.get("Item number") or "").strip()
        if item_id and item_id not in seen_ids:
            seen_ids.add(item_id)
            writer.writerow(["End", item_id, end_code])
            
    return output.getvalue()


# Truthful synonyms for "Natural" that match C:Gemstone Creation=Natural and
# C:Gemstone Treatment=Not Enhanced. Excludes unverifiable claims
# (Untreated/Certified/origin) per eBay search-manipulation policy.
NATURAL_SYNONYMS = ["Natural", "Genuine", "Real", "Authentic"]


def resolve_title_keyword(sku_id: int, title_variant: str = "rotate") -> str:
    """Deterministically resolve the Natural-slot keyword for a title.

    sku_id-based rotation keeps the same SKU on the same keyword across
    exports (reproducible, no random seed needed).
    """
    if (title_variant or "rotate").strip().lower() == "fixed":
        return NATURAL_SYNONYMS[0]
    try:
        idx = int(sku_id or 0) % len(NATURAL_SYNONYMS)
    except (ValueError, TypeError):
        idx = 0
    return NATURAL_SYNONYMS[idx]


def generate_ebay_creation_csv(
    items: List[Dict[str, Any]],
    gemstone_name: str = "Black Rutile Quartz",
    start_price: float = 9.99,
    schedule_start_time: str = "",
    is_pair: bool = False,
    transparency: str = "Transparent",
    title_variant: str = "rotate"
) -> str:
    """
    Generates official eBay Bulk Listing Creation CSV matching fx_category_template_EBAY_US schema.
    Includes 3 #INFO metadata headers, mandatory *Action header, 1-minute staggered scheduling,
    deterministic Natural-synonym title rotation, and <= 80 character title length guard.
    """
    from datetime import datetime, timedelta
    
    output = io.StringIO()
    
    # 1. Output #INFO Metadata Header Directives
    output.write("#INFO,Created=1752227834293,,,,,,,Indicates missing field that will be required soon,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,\n")
    output.write("#INFO,Version=1.0,,Template=fx_category_template_EBAY_US,,,,,Indicates field does not apply to this item/category,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,\n")
    output.write("#INFO,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,\n")
    
    writer = csv.writer(output)
    
    # 2. Main Header Row
    headers = [
        "*Action(SiteID=US|Country=IN|Currency=USD|Version=1193)",
        "Custom label (SKU)",
        "Category ID",
        "Category name",
        "Title",
        "Schedule Time",
        "Start price",
        "Quantity ",
        "Item photo URL",
        "VideoID",
        "Condition ID",
        "Description",
        "Format",
        "Duration",
        "Buy It Now price",
        "Best Offer Enabled",
        "Location",
        "Shipping profile name",
        "Return profile name",
        "Payment profile name",
        "C:Gemstone Type",
        "C:Gemstone Shape",
        "C:Item Length",
        "C:Item Width",
        "C:Item Depth",
        "C:Item Weight",
        "C:Gemstone Color",
        "C:Gemstone Creation",
        "C:Gemstone Form",
        "C:Country of Origin",
        "C:Country/Region of Manufacture",
        "C:Gemstone Treatment",
        "C:Certification",
        "C:Brand",
        "C:Cut Grade",
        "C:Gemstone Clarity Grade",
        "Gemstone name",
        "C:Transparency",
        "C:Wholesale = Yes, Private Message us",
        "C:Drillable = Free Drilling"
    ]
    writer.writerow(headers)
    
    # Handle schedule start time
    if schedule_start_time:
        try:
            base_dt = datetime.fromisoformat(schedule_start_time.replace('Z', '+00:00'))
        except Exception:
            base_dt = datetime.now()
    else:
        base_dt = datetime.now()
        
    description_html = '<a href="https://www.ebay.com/str/thegemsnjewels" target="_blank" style="text-align: center;"><h3><font color="#873d92">Thegemsnjewels</font></h3></a><h3 style="text-align: center;"><font color="#873d92">Shipping Policy</font></h3><h4 style="text-align: center;"><strong><font color="#873d92">US Shipping</font></strong></h4><ul><li><font color="#873d92"><strong>Cost</strong>: Free Shipping</font></li><li><font color="#873d92"><strong>Delivery Time</strong>: Generally within 15-20 days after shipping</font></li></ul><h4 style="text-align: center;"><strong><font color="#873d92">International Shipping</font></strong></h4><ul><li><font color="#873d92"><strong>Cost</strong>: Free Shipping</font></li><li><font color="#873d92"><strong>Delivery Time</strong>: Generally within 15-20 days worldwide</font></li></ul><h3 style="text-align: center;"><font color="#873d92">Return Policy</font></h3><p><font color="#873d92">Your satisfaction is our top priority. Returns accepted within 30 days.</font></p>'

    pair_str = "Pair " if is_pair else ""

    valid_idx = 0
    for item in items:
        if str(item.get("status") or "").upper() == "SOLD":
            continue
            
        group = (item.get("sku_group") or "").upper()
        sku_id = int(item.get("sku_id") or 0)
        sku_str = f"{group}-{sku_id:03d}"
        
        shape = (item.get("shape") or "Cabochon").strip().title()
        weight = float(item.get("weight") or 0.0)
        length = int(item.get("length") or 0)
        width = int(item.get("width") or 0)
        depth = int(item.get("depth") or 0)
        
        item_gem_name = (item.get("gemstone_name") or gemstone_name).strip()
        
        # Build Title with exact formula:
        # {weight} Ct {Natural|Genuine|Real|Authentic} {gem_name} {shape} Cabochon Loose Gemstone Pair {L}x{W}x{D} mm
        wt_str = f"{weight:.2f}".rstrip('0').rstrip('.')
        keyword = resolve_title_keyword(sku_id, title_variant)
        title = f"{wt_str} Ct. {keyword} {item_gem_name} {shape} Cabochon Loose Gemstone {pair_str}{length}x{width}x{depth} mm"
        
        # Enforce eBay <= 80 character Title limit
        if len(title) > 80:
            title = title[:80].strip()
            
        # Stagger publication time by 1 minute per row
        sched_dt = base_dt + timedelta(minutes=valid_idx)
        valid_idx += 1
        sched_str = sched_dt.strftime('%Y-%m-%dT%H:%M:%S+05:30')
        
        photo_a = f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_str}A.jpg"
        photo_b = f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_str}B.jpg"
        photos = f"{photo_a} | {photo_b}"
        
        item_price = float(item.get("start_price") or start_price)
        
        row = [
            "Add",
            sku_str,
            "262027",
            "/Jewelry & Watches/Loose Diamonds & Gemstones/Loose Gemstones",
            title,
            sched_str,
            f"{item_price:.2f}",
            "1",
            photos,
            "",
            "1500-New without tags",
            description_html,
            "FixedPrice",
            "GTC",
            "",
            "1",
            "302017",
            "Shipping",
            "Return - (ID: 136228479010)",
            "Payment - (ID: 232882248010)",
            item_gem_name,
            shape,
            f"{length} mm" if length > 0 else "",
            f"{width} mm" if width > 0 else "",
            f"{depth} mm" if depth > 0 else "",
            f"{weight:.2f} Ct." if weight > 0 else "",
            "",
            "Natural",
            "Polished",
            "India",
            "India",
            "Not Enhanced",
            "",
            "Unbranded",
            "Excellent",
            "Eye Clean",
            item_gem_name,
            transparency,
            "",
            ""
        ]
        writer.writerow(row)
        
    return output.getvalue()

