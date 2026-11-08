#!/usr/bin/env python3
"""Make the preview portable by embedding its local PNG references."""
from pathlib import Path
import base64

root = Path(__file__).resolve().parent
html = (root / "prototype.source.html").read_text()
for relative in (
    "assets/detail-1.png", "assets/detail-2.png",
    "assets/overview-1.png", "assets/overview-2.png",
    "reference/pi-perform.png", "reference/pi-browse.png",
):
    encoded = base64.b64encode((root / relative).read_bytes()).decode("ascii")
    html = html.replace(relative, "data:image/png;base64," + encoded)
(root / "index.html").write_text(html)

# A focused view for reviewing the loop overlay without starting playback.
loop_preview = html.replace(
    "</body>",
    """<script>document.querySelector('[data-deck="0"][data-control="loop"]').click();</script></body>""",
)
(root / "loop-preview.html").write_text(loop_preview)

# Show the taller source pane and its stationary toolbar toggle.
browse_preview = html.replace(
    "</body>",
    """<script>document.querySelector('[data-tab="browse"]').click();document.getElementById('show-sources').click();document.getElementById('source-pane').getAnimations().forEach(animation=>animation.finish());</script></body>""",
)
(root / "browse-preview.html").write_text(browse_preview)
