"""
Design primitives: parameterized infographics for Google Slides.
Each design generates batch update requests (createShape, insertText, groupObjects, etc.)
that can be applied via presentations_batch_update.
"""
from .base import EMU, SLIDE_W, SLIDE_H, hex_to_rgb_floats, resolve_colors
from .circular_process import generate_requests as circular_process_requests
from .grid import generate_requests as grid_requests
from .timeline import generate_requests as timeline_requests
from .process_flow import generate_requests as process_flow_requests

__all__ = [
    "EMU",
    "SLIDE_W",
    "SLIDE_H",
    "hex_to_rgb_floats",
    "resolve_colors",
    "process_flow_requests",
    "grid_requests",
    "circular_process_requests",
    "timeline_requests",
]
