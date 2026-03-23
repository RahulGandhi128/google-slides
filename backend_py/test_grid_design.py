"""
Test script: creates a Google Slides presentation with the stat-card grid infographic.
Run from backend_py/:  python test_grid_design.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from gws.tools import presentations_create, presentations_get, presentations_batch_update
from gws.designs.grid import generate_requests


def main():
    # 1. Create a new presentation
    print("Creating presentation...")
    result = presentations_create(title="Grid Infographic Test")
    if not isinstance(result, dict) or not result.get("presentationId"):
        print("Failed to create presentation:", result)
        sys.exit(1)

    pres_id = result["presentationId"]
    pres_url = result.get("presentationUrl", f"https://docs.google.com/presentation/d/{pres_id}/edit")
    print(f"Presentation created: {pres_url}")

    # 2. Get the first slide's page ID
    pres = presentations_get(pres_id)
    slides = pres.get("slides", [])
    if not slides:
        print("No slides found in presentation.")
        sys.exit(1)
    slide_id = slides[0]["objectId"]
    print(f"Using slide: {slide_id}")

    # 3. Build grid requests with theme colors and real content
    theme_colors = {
        "accent_color": "#3B82F6",
        "shapes_color": "#10B981",
        "charts_color": "#F59E0B",
        "heading_color": "#1E293B",
        "body_text_color": "#334155",
    }

    cells = [
        {
            "stat": "92%",
            "heading": "Customer Satisfaction",
            "body": "Our NPS score has consistently improved quarter over quarter, reflecting our commitment to user experience.",
            "bullets": [
                "Response time < 2 hours",
                "First-contact resolution 78%",
                "Support ticket volume -15%",
            ],
        },
        {
            "stat": "3.2x",
            "heading": "Revenue Growth",
            "body": "Year-over-year revenue has tripled driven by expansion into new markets and product lines.",
            "bullets": [
                "ARR crossed $50M milestone",
                "Enterprise deals +40%",
                "Churn rate reduced to 2.1%",
            ],
        },
        {
            "stat": "150+",
            "heading": "Team Members",
            "body": "Scaled from a 40-person startup to a global team across 4 offices in 18 months.",
            "bullets": [
                "Engineering 55%",
                "Product & Design 20%",
                "Sales & Marketing 25%",
            ],
        },
    ]

    print("Generating grid infographic requests...")
    requests = generate_requests(
        page_object_id=slide_id,
        columns=5,
        cells=cells,
        theme_colors=theme_colors,
        id_prefix="test_grid",
    )

    print(f"Generated {len(requests)} API requests.")

    # 4. Also add a title text box above the grid
    title_id = "test_title"
    requests.insert(0, {
        "createShape": {
            "objectId": title_id,
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "width": {"magnitude": 8_000_000, "unit": "EMU"},
                    "height": {"magnitude": 500_000, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1, "scaleY": 1,
                    "translateX": 572_000,
                    "translateY": 100_000,
                    "unit": "EMU",
                },
            },
        }
    })
    requests.insert(1, {
        "insertText": {
            "objectId": title_id,
            "text": "Q4 2025 — Company Performance Dashboard",
            "insertionIndex": 0,
        }
    })
    requests.insert(2, {
        "updateTextStyle": {
            "objectId": title_id,
            "style": {
                "foregroundColor": {"opaqueColor": {"rgbColor": {"red": 0.118, "green": 0.161, "blue": 0.231}}},
                "fontSize": {"magnitude": 22, "unit": "PT"},
                "bold": True,
            },
            "fields": "foregroundColor,fontSize,bold",
        }
    })

    # 5. Send batch update
    print("Sending batch update...")
    try:
        presentations_batch_update(pres_id, requests)
        print("Done! Open your presentation:")
        print(f"  {pres_url}")
    except Exception as e:
        print(f"Batch update failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
