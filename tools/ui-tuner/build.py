#!/usr/bin/env python3
"""Build a portable, non-operational field-review page from pinned evidence."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
OVERLAY_SHA256 = 'dc4c5f79480f2fa8a25ad9ee14c8a7054991e56089d1431a43844438fbb659e6'
DEFAULT_OVERLAY = ROOT / 'deploy/recovery-20261110/settings-incremental-candidate/artifacts/pioneered-tools-overlay.tar.gz'
PHOTO_NAMES = ('0263', '0264', '0265', '0257', '0258', '0259', '0260', '0261', '0262', '0256')
NATIVE_SCREENS = (
    ('13-browse-settled.png', 'Browse · confirmed missing dark style scope'),
    ('06-fx-selector.png', 'Effects · selector popup'),
    ('15-fx-settled.png', 'Effects · settled sliders'),
    ('16-sampler-settled.png', 'Sampler · four pads'),
    ('17-settings-settled.png', 'Settings · settled controls'),
    ('09-load-dialog.png', 'LOAD · actual chooser'),
    ('12-eject-dialog.png', 'EJECT · actual OFF-profile denial'),
    ('18-perform-restored.png', 'Perform · final restored view'),
)
TEMPLATE = Path(__file__).with_name('tuner.source.html')


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def image_record(path, mime):
    payload = path.read_bytes()
    if len(payload) > 10 * 1024 * 1024:
        raise ValueError(f'Image too large: {path.name}')
    signature = b'\xff\xd8' if mime == 'image/jpeg' else b'\x89PNG\r\n\x1a\n'
    if not payload.startswith(signature):
        raise ValueError(f'Unexpected image signature: {path.name}')
    return {'name': path.name, 'sha256': digest(payload),
            'url': f'data:{mime};base64,' + base64.b64encode(payload).decode('ascii')}


def read_member(archive, name):
    matches = [member for member in archive.getmembers() if member.name == name]
    if len(matches) != 1 or not matches[0].isfile() or matches[0].size > 512 * 1024:
        raise ValueError(f'Expected one bounded regular member: {name}')
    return archive.extractfile(matches[0]).read()


def native_record(directory):
    payload = (directory / 'live-inventory-final.json').read_bytes()
    if len(payload) > 2 * 1024 * 1024:
        raise ValueError('Native inventory exceeds the review size limit')
    inventory = json.loads(payload)
    fields = ('observedAt', 'bootId', 'binarySha256')
    if not isinstance(inventory, dict) or any(
            not isinstance(inventory.get(key), str) or not inventory[key] for key in fields):
        raise ValueError('Native inventory lacks capture provenance')
    return {**{key: inventory[key] for key in fields}, 'inventorySha256': digest(payload),
            'screens': [{**image_record(directory / 'screens' / name, 'image/png'),
                         'label': label} for name, label in NATIVE_SCREENS]}


def build(photos, overlay=DEFAULT_OVERLAY, native_evidence=None):
    payload = overlay.read_bytes()
    if digest(payload) != OVERLAY_SHA256:
        raise ValueError('Overlay identity differs from the accepted field baseline')
    with tarfile.open(overlay, 'r:gz') as archive:
        skin = read_member(archive, './usr/share/mixxx/skins/Pioneered/skin.xml')
        style = read_member(archive, './usr/share/mixxx/skins/Pioneered/style.qss')
    root = ET.fromstring(skin)
    baseline = {
        'schemaVersion': 1,
        'overlaySha256': OVERLAY_SHA256,
        'skinSha256': digest(skin),
        'styleSha256': digest(style),
        'libraryWrapperCount': sum(element.text == 'LibraryWrapper'
                                   for element in root.findall('.//ObjectName')),
        'scopedLibraryStylePresent': '#LibraryWrapper QTableView' in style.decode('utf-8'),
        'geometry': {'width': 800, 'height': 480, 'desktopBar': 36, 'applicationHeight': 444},
        'photos': [image_record(photos / f'IMG_{name}.jpg', 'image/jpeg') for name in PHOTO_NAMES],
        'historical': image_record(ROOT / 'tools/pioneer-prototype/reference/pi-browse.png', 'image/png'),
        'native': native_record(native_evidence) if native_evidence is not None else None,
        'inputs': {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in (
            TEMPLATE, Path(__file__),
            ROOT / 'stage3/01-install-packages/files/mixpi-performance.py',
            ROOT / 'stage3/01-install-packages/files/mixpi-performance.qss',
            ROOT / 'stage3/01-install-packages/files/pioneered-touch.qss',
            ROOT / 'stage3/01-install-packages/files/pioneered-menus.qss')},
    }
    template = TEMPLATE.read_text()
    if template.count('__BASELINE_JSON__') != 1:
        raise ValueError('Expected exactly one baseline placeholder')
    encoded = json.dumps(baseline, separators=(',', ':')).replace('<', '\\u003c')
    return template.replace('__BASELINE_JSON__', encoded), baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--photos', type=Path, required=True)
    parser.add_argument('--overlay', type=Path, default=DEFAULT_OVERLAY)
    parser.add_argument('--native-evidence', type=Path,
                        help='Captured field-live directory; never contacts the Pi')
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    html, baseline = build(options.photos, options.overlay, options.native_evidence)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = options.output.with_suffix('.html.tmp')
    temporary.write_text(html)
    temporary.replace(options.output)
    receipt = {key: value for key, value in baseline.items() if key not in ('photos', 'historical')}
    receipt['photos'] = [{key: value for key, value in photo.items() if key != 'url'}
                         for photo in baseline['photos']]
    receipt['historical'] = {key: value for key, value in baseline['historical'].items() if key != 'url'}
    if baseline['native'] is not None:
        receipt['native'] = {**baseline['native'], 'screens': [
            {key: value for key, value in screen.items() if key != 'url'}
            for screen in baseline['native']['screens']]}
    receipt['htmlSha256'] = digest(html.encode())
    options.output.with_suffix('.baseline.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'Built {options.output}; preview only, no native acceptance or Pi changes.')


if __name__ == '__main__':
    main()
