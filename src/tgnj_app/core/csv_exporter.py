import csv
from io import StringIO
from typing import List, Dict, Any

def generate_vela_csv(items: List[Dict[Any, Any]], gemstone_name: str = "Black Tourmailne Rutile Quartz") -> str:
    """
    Generates an exact 33-column Vela-compatible CSV string for bulk listing upload to Etsy/Vela.
    Expects items with keys: sku_group, sku_id, shape, weight, length, width, depth, etsy_price
    """
    output = StringIO()
    writer = csv.writer(output)
    
    headers = [
        "Title",
        "Description",
        "Category",
        "Who made it?",
        "What is it?",
        "When was it made?",
        "Renewal options",
        "Product type",
        "Tags",
        "Materials",
        "Production partners",
        "Section",
        "Price",
        "Quantity",
        "SKU",
        "Shipping profile",
        "Return policy",
        "Photo 1",
        "Photo 2",
        "Photo 3",
        "Photo 4",
        "Photo 5",
        "Photo 6",
        "Photo 7",
        "Photo 8",
        "Photo 9",
        "Photo 10",
        "Shape",
        "item Length",
        "Item width",
        "Item Depth",
        "Weight",
        "Gemstone Name"
    ]
    writer.writerow(headers)
    
    for item in items:
        group = item.get("sku_group", "").upper()
        sku_id = item.get("sku_id", 0)
        sku_str = f"{group}-{int(sku_id):03d}"
        
        shape = (item.get("shape") or "").strip().title()
        weight = float(item.get("weight") or 0.0)
        length = int(item.get("length") or 0)
        width = int(item.get("width") or 0)
        depth = int(item.get("depth") or 0)
        price = float(item.get("etsy_price") or 0.0)
        if price <= 0:
            price = 12.99
            
        gem_name = item.get("gemstone_name") or gemstone_name
        title = f"{weight:.2f} Ct.Natural High Quality {gem_name} Loose Gemstone {shape} Cabochon For Jewelry Making"
        
        description = (
            f"Natural {gem_name} Cabochon - High Quality Loose Gemstone\n\n"
            f"PRODUCT OVERVIEW\n"
            f"This listing is for a premium, hand-polished {gem_name} cabochon. Known for its striking contrast, "
            f"this natural clear quartz is filled with needle-like inclusions of Black Tourmaline (Rutile), creating a unique \"matrix\" or \"spider-web\" effect. "
            f"No two stones are ever exactly alike, making this a truly one-of-a-kind piece for your next jewelry project.\n\n"
            f"SPECIFICATIONS\n\n"
            f"Gemstone: Natural {gem_name}\n"
            f"Treatment: 100% Natural and Untreated\n\n"
            f"METAPHYSICAL PROPERTIES\n"
            f"{gem_name} is often called the \"stone of power.\" It is believed to be a strong grounding stone that clears energy blockages and protects the wearer from negativity. "
            f"Its unique balance of clear quartz and dark inclusions makes it a symbol of the union between light and shadow.\n\n"
            f"IDEAL USES\n"
            f"This stone is perfectly suited for custom rings, statement pendants, or boho-style earrings. "
            f"It is also a popular choice for crystal healing collections, meditation altars, or as a unique gift for gemstone collectors."
        )
        
        tags = "Black Rutile Quartz, Rutilated Quartz, Loose Gemstone, Cabochon for Ring, Jewelry Making, Black Tourmaline, Natural Stone, Healing Crystal, DIY Jewelry, Oval Cabochon, Unique Gemstone, Black Inclusions, Gemstone Supply"
        materials = "Natural Black Rutilated Quartz, Black Tourmaline Inclusions, Hand Polished Cabochon, Untreated Gemstone, AAA Grade Quartz, Earth Mined Stone, Solid Crystal, Genuine Rutile, Flat Back Stone, Jewelry Grade Gem, High Quality Rutile, Black Needle Quartz, Natural Quartz Crystal"
        
        photo1 = f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_str}A.jpg"
        photo2 = f"https://tgnj-pictures.s3.us-east-1.amazonaws.com/{group}/{sku_str}B.jpg"
        
        writer.writerow([
            title,
            description,
            "Craft Supplies & Tools > Beads, Gems & Cabochons > Gemstones",
            "A member of my shop",
            "A finished product",
            "2020 - 2026",
            "Manual",
            "Physical",
            tags,
            materials,
            "", # Production partners
            "", # Section
            f"{price:.2f}",
            "1",
            sku_str,
            "Normal Shipping",
            "30 days to return or exchange",
            photo1,
            photo2,
            "", "", "", "", "", "", "", "", # Photo 3 to 10
            shape,
            f"{length} mm",
            f"{width} mm",
            f"{depth} mm",
            f"{weight:.2f} Ct.",
            gem_name
        ])
        
    return output.getvalue()
