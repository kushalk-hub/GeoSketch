"""GeoSketch route-art engine.

Pipeline::

    GPS points -> validation -> redundancy filter -> gap/jump segmentation
               -> local projection -> canvas normalisation -> art spec
               -> SVG renderer + PNG renderer

No machine learning and no paid service is involved: the artwork is produced
with ordinary vector/raster graphics primitives.
"""

from app.artwork.engine import RenderResult, render_route_art
from app.artwork.geometry import ProcessedRoute, process_route
from app.artwork.styles import ArtSpec, ArtworkStyle

__all__ = [
    "ArtSpec",
    "ArtworkStyle",
    "ProcessedRoute",
    "RenderResult",
    "process_route",
    "render_route_art",
]
