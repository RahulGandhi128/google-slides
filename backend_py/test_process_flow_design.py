"""
Test script: creates a Google Slides presentation with the chevron process-flow infographic.
Run from backend_py/:  python test_process_flow_design.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from gws.tools import presentations_create, presentations_get, presentations_batch_update
from gws.designs.process_flow import generate_requests


def main():
    # 1. Create a new presentation
    print("Creating presentation...")
    result = presentations_create(title="Process Flow Infographic Test")
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

    # 3. Build process flow with theme colors and rich step data
    theme_colors = {
        "accent_color": "#6366F1",
        "shapes_color": "#8B5CF6",
        "charts_color": "#A855F7",
        "heading_color": "#1E1B4B",
        "body_text_color": "#334155",
    }

    steps = [
        {
            "label": "Discovery",
            "body": "Identify stakeholder needs through interviews, surveys, and market analysis. Define project scope, goals, and success metrics.",
        },
        {
            "label": "Design",
            "body": "Create wireframes, user flows, and high-fidelity mockups. Iterate based on stakeholder feedback and usability testing results.",
        },
        {
            "label": "Develop",
            "body": "Build frontend and backend components with CI/CD pipelines. Conduct code reviews, unit tests, and integration testing.",
        },
        {
            "label": "Deploy",
            "body": "Roll out to staging, run smoke tests, then promote to production. Monitor error rates, latency, and user engagement post-launch.",
        },
    ]

    print("Generating process flow requests...")
    requests = generate_requests(
        page_object_id=slide_id,
        steps=steps,
        theme_colors=theme_colors,
        id_prefix="test_proc",
    )
    print(f"Generated {len(requests)} API requests.")

    # 4. Add a title text box above the flow
    title_id = "test_proc_title"
    requests.insert(0, {
        "createShape": {
            "objectId": title_id,
            "shapeType": "TEXT_BOX",
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {
                    "width": {"magnitude": 8_000_000, "unit": "EMU"},
                    "height": {"magnitude": 420_000, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1, "scaleY": 1,
                    "translateX": 572_000,
                    "translateY": 80_000,
                    "unit": "EMU",
                },
            },
        }
    })
    requests.insert(1, {
        "insertText": {
            "objectId": title_id,
            "text": "Product Development Lifecycle",
            "insertionIndex": 0,
        }
    })
    requests.insert(2, {
        "updateTextStyle": {
            "objectId": title_id,
            "style": {
                "foregroundColor": {"opaqueColor": {"rgbColor": {"red": 0.118, "green": 0.106, "blue": 0.294}}},
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
