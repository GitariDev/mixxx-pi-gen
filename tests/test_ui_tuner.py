"""Portable review preparation checks; these do not qualify native Qt behavior."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ui_tuner', ROOT / 'tools/ui-tuner/build.py')
TUNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TUNER)


class UiTunerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.photos = self.root / 'photos'
        self.photos.mkdir()
        for name in TUNER.PHOTO_NAMES:
            (self.photos / f'IMG_{name}.jpg').write_bytes(b'\xff\xd8fixture')
        self.overlay = self.root / 'overlay.tar.gz'
        with tarfile.open(self.overlay, 'w:gz') as archive:
            for name, payload in (
                ('skin.xml', b'<skin><ObjectName>MixpiLibraryMain</ObjectName></skin>'),
                ('style.qss', b'#LibraryWrapper QTableView { color: white; }')):
                member = tarfile.TarInfo('./usr/share/mixxx/skins/Pioneered/' + name)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
        self.pin = hashlib.sha256(self.overlay.read_bytes()).hexdigest()

    def build(self, native_evidence=None):
        with mock.patch.object(TUNER, 'OVERLAY_SHA256', self.pin):
            return TUNER.build(self.photos, self.overlay, native_evidence)

    def native_fixture(self):
        directory = self.root / 'native'
        (directory / 'screens').mkdir(parents=True)
        inventory = {'observedAt': '2026-11-11T11:09:33+00:00',
                     'bootId': 'd5134a03-b3f5-4876-962f-d96c0cb10eae',
                     'binarySha256': '01b56633a966ab1031aeaaace6bce11eb3068ad0f76bd31a007bb0e20cbd6778',
                     'privateProfile': 'must not be embedded'}
        (directory / 'live-inventory-final.json').write_text(json.dumps(inventory))
        for name, _ in TUNER.NATIVE_SCREENS:
            (directory / 'screens' / name).write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        return directory

    def test_actual_native_captures_and_inventory_are_bound_without_private_profile(self):
        directory = self.native_fixture()
        html, baseline = self.build(directory)
        native = baseline['native']
        self.assertEqual(len(native['screens']), 8)
        self.assertEqual(native['bootId'], 'd5134a03-b3f5-4876-962f-d96c0cb10eae')
        self.assertEqual(native['inventorySha256'], hashlib.sha256(
            (directory / 'live-inventory-final.json').read_bytes()).hexdigest())
        self.assertNotIn('privateProfile', html)
        self.assertNotIn('must not be embedded', html)
        self.assertIn('native:baseline.native', html)
        self.assertIn('Captured on', html)
        self.assertNotIn('No remote Pi profile has been read.', html)

    def test_requested_native_evidence_must_be_complete(self):
        directory = self.native_fixture()
        (directory / 'screens' / TUNER.NATIVE_SCREENS[0][0]).unlink()
        with self.assertRaises(FileNotFoundError):
            self.build(directory)

    def test_photo_only_tuner_does_not_claim_native_evidence(self):
        _, baseline = self.build()
        self.assertIsNone(baseline['native'])

    def test_native_inventory_requires_provenance_and_has_size_bound(self):
        directory = self.native_fixture()
        inventory = directory / 'live-inventory-final.json'
        for payload in ('{}', '[]', '{"observedAt":12}', ' ' * (2 * 1024 * 1024 + 1)):
            with self.subTest(payload=payload[:30]):
                inventory.write_text(payload)
                with self.assertRaises(ValueError):
                    self.build(directory)

    def test_complete_photo_and_historical_binding_is_embedded(self):
        html, baseline = self.build()
        self.assertEqual(len(baseline['photos']), 10)
        self.assertEqual(baseline['libraryWrapperCount'], 0)
        self.assertTrue(baseline['scopedLibraryStylePresent'])
        self.assertEqual(baseline['geometry']['applicationHeight'], 444)
        self.assertIn('data:image/png;base64,', html)
        self.assertIn('data:image/jpeg;base64,', html)
        self.assertNotIn('__BASELINE_JSON__', html)
        encoded = re.search(r'<script id="baseline" type="application/json">(.*?)</script>', html).group(1)
        self.assertEqual(json.loads(encoded), baseline)

    def test_wrong_overlay_is_rejected_before_preview_generation(self):
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            TUNER.build(self.photos, self.overlay)

    def test_missing_photo_is_not_substituted_with_a_simulation(self):
        (self.photos / 'IMG_0263.jpg').unlink()
        with self.assertRaises(FileNotFoundError):
            self.build()

    def test_invalid_image_is_rejected(self):
        (self.photos / 'IMG_0263.jpg').write_bytes(b'<html>not a photo</html>')
        with self.assertRaisesRegex(ValueError, 'signature'):
            self.build()

    def test_archive_member_type_duplicates_and_size_are_rejected(self):
        for variant in ('symlink', 'duplicate', 'oversize'):
            with self.subTest(variant=variant):
                archive_path = self.root / f'{variant}.tar'
                with tarfile.open(archive_path, 'w') as archive:
                    member = tarfile.TarInfo('style.qss')
                    if variant == 'symlink':
                        member.type = tarfile.SYMTYPE
                        member.linkname = '/etc/passwd'
                        archive.addfile(member)
                    else:
                        payload = b'x' * (512 * 1024 + 1 if variant == 'oversize' else 1)
                        member.size = len(payload)
                        archive.addfile(member, io.BytesIO(payload))
                        if variant == 'duplicate':
                            archive.addfile(member, io.BytesIO(payload))
                with tarfile.open(archive_path) as archive:
                    with self.assertRaisesRegex(ValueError, 'regular member'):
                        TUNER.read_member(archive, 'style.qss')

    def test_preview_has_no_external_assets_or_operational_api(self):
        html, _ = self.build()
        self.assertIn("connect-src 'none'", html)
        self.assertIn('approved:false,nativeValidated:false', html)
        self.assertIn('No mount, unmount, power-off or authority change', html)
        self.assertNotRegex(html, r'(?:src|href)=[\"\']https?://')
        self.assertNotRegex(html, r'\b(?:fetch|WebSocket|XMLHttpRequest)\s*\(')
        self.assertNotIn('localStorage', html)
        self.assertIn('.screen [hidden]{display:none!important}', html)

    @unittest.skipUnless(shutil.which('node'), 'Node required for preview JavaScript syntax check')
    def test_generated_javascript_parses(self):
        html, _ = self.build()
        script = re.search(r'<script>\n(.*?)</script>', html, re.S).group(1)
        script_path = self.root / 'preview.js'
        script_path.write_text(script)
        result = subprocess.run(['node', '--check', str(script_path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def run_workshop_assertions(self, assertions):
        if not shutil.which('node'):
            self.skipTest('Node required for workshop state tests')
        html, baseline = self.build()
        script = re.search(r'<script>\n(.*?)</script>', html, re.S).group(1)
        harness = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const nodes = new Map();
function node(name) {
    if (!nodes.has(name)) nodes.set(name, {
        value: '', textContent: '', innerHTML: '', dataset: {}, hidden: false,
        listeners: {}, style: {setProperty() {}}, classList: {toggle() {}},
        append() {}, focus() {}, setAttribute() {}, click() {},
        addEventListener(type, callback) { this.listeners[type] = callback; },
        querySelector(selector) { return node(selector); }
    });
    return nodes.get(name);
}
const controls = {font:17,row:34,pane:290,rail:8,thumb:20,columns:'classic',
    selection:'classic','settings-style':'grouped','media-scenario':'off'};
for (const [name,value] of Object.entries(controls)) node(name).value=String(value);
node('baseline').textContent=JSON.stringify(BASELINE);
node('saved-draft').textContent='null';
const context = {assert,node,console,document:{getElementById:node,
    createElement:() => node('created'),querySelectorAll:()=>[],querySelector:()=>null},
    ResizeObserver:class {observe() {}},confirm:()=>true,setTimeout:()=>{},
    Blob:class {constructor(parts,options){this.parts=parts;this.options=options;}},
    URL:{createObjectURL(blob){context.downloaded=blob;return 'blob:fixture';},revokeObjectURL(){}}};
vm.runInNewContext(SCRIPT+'\n'+ASSERTIONS,context);
"""
        program = ('const BASELINE=' + json.dumps(baseline) + ';\nconst SCRIPT='
                   + json.dumps(script) + ';\nconst ASSERTIONS='
                   + json.dumps(assertions) + ';\n' + harness)
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_sources_menu_keeps_multiple_selections_separate_from_show(self):
        self.run_workshop_assertions("""
act('show');
assert.equal(menu,null); assert.equal(sourcesVisible,true);
assert.ok(tracks().includes('Files and folders overlay'));
assert.ok(tracks().includes('source-back'));assert.ok(tracks().includes('Sources ▾'));
const toolbar=tracks().split('<div class="browse-body">')[0];
assert.ok(toolbar.includes('data-action="actions"'));assert.ok(toolbar.includes('data-action="show"'));
assert.ok(!toolbar.includes('data-action="sources"'));
assert.ok(sourcePane().indexOf('data-action="sources"')<sourcePane().indexOf('data-action="source-back"'));
assert.ok(sourcePane().includes('data-action="sources" aria-expanded="false"'));
act('sources');
assert.ok(sourcePane().includes('data-action="sources" aria-expanded="true"'));
for(const name of ['Auto DJ','History'])node('screen').listeners.change({target:{dataset:{source:name},checked:false}});
assert.equal(menu,'sources');assert.ok(!visibleSources.includes('Auto DJ'));
assert.ok(!visibleSources.includes('History'));
assert.ok(!node('preview-menu').innerHTML.includes('Track titles'));
assert.ok(node('preview-menu').innerHTML.includes('Close'));
act('close-menu'); assert.equal(menu,null); assert.equal(sourcesVisible,true);
act('show');assert.equal(sourcesVisible,false);
assert.ok(!tracks().includes('Files and folders overlay'));
""")

    def test_folder_back_overlay_navigation_and_visibility_safety(self):
        self.run_workshop_assertions("""
act('show');
node('screen').listeners.click({target:{closest(selector){return selector==='[data-source-entry]'?{dataset:{sourceEntry:'Computer'}}:null;}}});
openSource('computer-music');openSource('copied-library');
assert.deepEqual([...sourcePath],['Computer','computer-music','copied-library']);
assert.ok(tracks().includes('Computer / Music / Copied library'));
act('show');act('show');assert.equal(sourcePath.length,3);
act('source-back');assert.equal(sourcePath.length,2);
openSource('<script>');openSource('Rekordbox');assert.equal(sourcePath.length,2);
currentPage='fx';render();currentPage='browse';render();assert.equal(sourcePath.length,2);
act('sources');node('screen').listeners.change({target:{dataset:{source:'Computer'}}});
assert.equal(sourcePath.length,0);assert.equal(menu,'sources');
visibleSources=['Tracks'];node('screen').listeners.change({target:{dataset:{source:'Tracks'}}});
assert.deepEqual([...visibleSources],['Tracks']);
act('source-back');assert.deepEqual([...sourcePath],[]);
assert.equal(validSourcePath(['Computer','../../etc']),false);
""")

    def test_columns_reorder_visibility_and_last_column_safety(self):
        self.run_workshop_assertions("""
assert.deepEqual([...moveColumn(initialOrder,'artist',-1)],['artist','title','bpm','key','played']);
assert.deepEqual([...moveColumn(initialOrder,'title',-1)],[...initialOrder]);
assert.deepEqual([...moveColumn(initialOrder,'missing',1)],[...initialOrder]);
assert.deepEqual([...toggleColumn(['title'],'title')],['title']);
assert.deepEqual([...toggleColumn(['title'],'injected')],['title']);
columnOrder=moveColumn(initialOrder,'artist',-1);
visibleColumns=toggleColumn(['title','artist'],'title');
assert.ok(tracks().includes('<th>Artist</th>'));assert.ok(!tracks().includes('<th>Title</th>'));
act('columns');assert.equal(menu,'columns');assert.ok(node('preview-menu').innerHTML.includes('Move Artist later'));
""")

    def test_effect_selector_stays_a_native_dropdown_with_text_only_placeholder(self):
        self.run_workshop_assertions("""
currentPage='fx';render();
assert.equal(node('preview-menu').hidden,true);
assert.equal((effects().match(/<select class="effect-choice"/g)||[]).length,3);
assert.ok(effects().includes('Select effect…'));
assert.ok(!effects().includes('data-action="effect-'));
assert.ok(!effects().includes('BEAT FX'));assert.ok(!effects().includes('Choose effect'));
node('screen').listeners.change({target:{dataset:{effectSlot:'2'},value:'PHASER'}});
assert.equal(selectedEffects[2],'PHASER');assert.equal(menu,null);
node('screen').listeners.change({target:{dataset:{effectSlot:'99'},value:'FILTER'}});
node('screen').listeners.change({target:{dataset:{effectSlot:'2'},value:'<img>'}});
assert.equal(selectedEffects.length,3);assert.equal(selectedEffects[2],'PHASER');
""")

    def test_media_stays_non_operational(self):
        self.run_workshop_assertions("""
currentPage='media';render();
assert.ok(media().includes('<button disabled>Eject unavailable</button>'));
assert.ok(!media().includes('safe to remove'));
assert.equal(mediaPresentation('in-use').action,null);
assert.equal(mediaPresentation('unknown').action,null);
assert.equal(mediaPresentation('unrecognized').action,null);
assert.equal(mediaPresentation('available').action,'load-source');
act('drive-internal');act('load-source');assert.ok(feedback.includes('No files opened'));
act('close-media');assert.equal(currentPage,'browse');
""")

    def test_draft_roundtrip_rejects_bad_data_before_changing_state(self):
        self.run_workshop_assertions("""
columnOrder=moveColumn(columnOrder,'key',-1);sourcesVisible=true;
screenNotes.fx='Keep the mix box';node('notes').value='Owner notes';
const record=draftRecord();restoreDraft(record);
assert.equal(sourcesVisible,true);assert.equal(screenNotes.fx,'Keep the mix box');
assert.equal(node('notes').value,'Owner notes');
const invalid=JSON.parse(JSON.stringify(record));invalid.preferences.visibleColumns=[];
assert.throws(()=>restoreDraft(invalid),/visible columns/);assert.equal(sourcesVisible,true);
const wrong=JSON.parse(JSON.stringify(record));wrong.baseline.skinSha256='wrong';
assert.throws(()=>restoreDraft(wrong),/baseline/);
const injected=JSON.parse(JSON.stringify(record));injected.preferences.columnOrder[0]='<img>';
assert.throws(()=>restoreDraft(injected),/column order/);
const approved=JSON.parse(JSON.stringify(record));approved.approved=true;
assert.throws(()=>restoreDraft(approved),/unapproved/);
""")

    def test_html_save_escapes_script_notes_and_restores_keyboard_close(self):
        self.run_workshop_assertions(r"""
const cloneNodes=new Map();
const root={querySelector(selector){if(!cloneNodes.has(selector))cloneNodes.set(selector,{textContent:'',replaceChildren(){this.cleared=true;}});return cloneNodes.get(selector);},get outerHTML(){return '<html>'+this.querySelector('#saved-draft').textContent+'</html>';}};
document.documentElement={cloneNode(){return root;}};
node('notes').value='</script><script>alert(1)</script>&';
showDesktop=false;openSource('Computer');
node('save-html').listeners.click();
const saved=root.querySelector('#saved-draft').textContent;
assert.ok(!saved.includes('<'));assert.ok(!saved.includes('&'));
assert.equal(JSON.parse(saved).notes,node('notes').value);
assert.equal(JSON.parse(saved).preferences.showDesktop,false);
assert.deepEqual([...JSON.parse(saved).view.sourcePath],['Computer']);
assert.ok(root.querySelector('#photo').cleared);assert.ok(root.querySelector('#native-screen').cleared);assert.ok(root.querySelector('#transport').cleared);
restoreDraft(JSON.parse(saved));assert.equal(node('notes').value,JSON.parse(saved).notes);
act('sources');let prevented=false;
node('screen').listeners.keydown({key:'Escape',preventDefault(){prevented=true;},target:{closest(){return null;}}});
assert.equal(menu,null);assert.equal(prevented,true);
""")

    def test_tempo_options_and_advanced_settings_are_separate(self):
        self.run_workshop_assertions("""
assert.ok(settings().includes('90%'));assert.ok(!settings().includes('READ-AHEAD'));
act('advanced');assert.ok(settings().includes('READ-AHEAD'));assert.ok(!settings().includes('TEMPO ±'));
currentPage='browse';render();assert.equal(node('transport').hidden,true);
currentPage='decks';render();assert.equal(node('transport').hidden,false);
""")

    def test_desktop_bar_reclaims_space_and_remains_restorable(self):
        self.run_workshop_assertions("""
currentPage='settings';render();assert.ok(settings().includes('Hide top bar'));
assert.equal(node('native-main').style.height,'314px');act('desktop-bar');
assert.equal(showDesktop,false);assert.equal(node('.desktop').hidden,true);
assert.equal(node('native-main').style.height,'350px');
assert.equal(node('preview-menu').style.top,'98px');
assert.ok(settings().includes('Show top bar'));
for(const page of ['browse','fx','media','startup']){currentPage=page;render();assert.equal(node('native-main').style.height,'350px');}
currentPage='decks';render();assert.equal(node('native-main').style.height,'244px');
currentPage='settings';render();act('desktop-bar');
assert.equal(showDesktop,true);assert.equal(node('.desktop').hidden,false);
assert.equal(node('native-main').style.height,'314px');
assert.equal(node('preview-menu').style.top,'134px');
""")

    def test_new_settings_and_folder_path_persist_with_older_draft_migration(self):
        self.run_workshop_assertions("""
showDesktop=false;openSource('Computer');openSource('computer-music');
screenNotes.settings='Keep this toggle';const record=draftRecord();restoreDraft(record);
assert.equal(showDesktop,false);assert.deepEqual([...sourcePath],['Computer','computer-music']);
assert.equal(screenNotes.settings,'Keep this toggle');
for(const invalidValue of ['false',null,1]){const invalid=JSON.parse(JSON.stringify(record));invalid.preferences.showDesktop=invalidValue;assert.throws(()=>restoreDraft(invalid),/desktop bar/);}
const invalidPath=JSON.parse(JSON.stringify(record));invalidPath.view.sourcePath=['Computer','<img>'];
assert.throws(()=>restoreDraft(invalidPath),/source path/);assert.equal(sourcePath.length,2);
const older=JSON.parse(JSON.stringify(record));older.uiRevision=2;
delete older.preferences.showDesktop;delete older.view.sourcePath;
restoreDraft(older);assert.equal(showDesktop,true);assert.equal(sourcePath.length,0);
assert.equal(screenNotes.settings,'Keep this toggle');
showDesktop=false;openSource('Computer');node('reset').listeners.click();
assert.equal(showDesktop,true);assert.equal(sourcePath.length,0);
""")


if __name__ == '__main__':
    unittest.main()
