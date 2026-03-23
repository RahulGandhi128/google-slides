"""
Test script: creates a Google Slides presentation with the timeline infographic.

Run from backend_py/:  python test_timeline_design.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from gws.tools import presentations_create, presentations_get, presentations_batch_update
from gws.designs.timeline import generate_requests


def main():
    print("Creating presentation...")
    result = presentations_create(title="Timeline Infographic Test")
    if not isinstance(result, dict) or not result.get("presentationId"):
        print("Failed to create presentation:", result)
        sys.exit(1)

    pres_id = result["presentationId"]
    pres_url = result.get("presentationUrl", f"https://docs.google.com/presentation/d/{pres_id}/edit")
    print(f"Presentation created: {pres_url}")

    pres = presentations_get(pres_id)
    slides = pres.get("slides", [])
    if not slides:
        print("No slides found in presentation.")
        sys.exit(1)
    slide_id = slides[0]["objectId"]
    print(f"Using slide: {slide_id}")

    theme_colors = {
        "accent_color": "#22C55E",
        "shapes_color": "#10B981",
        "charts_color": "#0EA5E9",
        "heading_color": "#0F172A",
        "body_text_color": "#334155",
    }

    events = [
        {
            "year": "2019",
            "heading": "Foundation",
            "body": "Define the roadmap, align stakeholders, and set up the initial architecture.",
        },
        {
            "year": "2020",
            "heading": "Prototype",
            "body": "Build a working prototype, validate assumptions, and collect user feedback.",
        },
        {
            "year": "2021",
            "heading": "Scale",
            "body": "Improve performance, ship major features, and expand to new teams and use cases.",
        },
        {
            "year": "2022",
            "heading": "Optimize",
            "body": "Refine the product experience, reduce operational overhead, and enhance reliability.",
        },
        {
            "year": "2023",
            "heading": "Innovation",
            "body": "Introduce next-gen capabilities and continuously iterate on the customer journey.",
        },
    ]

    print("Generating timeline infographic requests...")
    requests = generate_requests(
        page_object_id=slide_id,
        events=events,
        theme_colors=theme_colors,
        id_prefix="test_timeline",
    )
    print(f"Generated {len(requests)} API requests.")

    # Title above the timeline
    title_id = "test_timeline_title"
    requests.insert(
        0,
        {
            "createShape": {
                "objectId": title_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {
                        "width": {"magnitude": 8_200_000, "unit": "EMU"},
                        "height": {"magnitude": 420_000, "unit": "EMU"},
                    },
                    "transform": {
                        "scaleX": 1,
                        "scaleY": 1,
                        "translateX": 350_000,
                        "translateY": 80_000,
                        "unit": "EMU",
                    },
                },
            }
        },
    )
    requests.insert(
        1,
        {
            "insertText": {
                "objectId": title_id,
                "text": "Product Timeline",
                "insertionIndex": 0,
            }
        },
    )
    requests.insert(
        2,
        {
            "updateTextStyle": {
                "objectId": title_id,
                "style": {
                    "foregroundColor": {
                        "opaqueColor": {"rgbColor": {"red": 0.1, "green": 0.16, "blue": 0.25}}
                    },
                    "fontSize": {"magnitude": 22, "unit": "PT"},
                    "bold": True,
                },
                "fields": "foregroundColor,fontSize,bold",
            }
        },
    )

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

