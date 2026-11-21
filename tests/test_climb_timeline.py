"""Climb timeline checks: the schema on the real data, broken samples, and the standalone HTML."""

import contextlib
import copy
import io
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('climb_timeline', ROOT / 'tools/climb-timeline/build.py')
TIMELINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TIMELINE)
# The untracked evidence lives in the main checkout's deploy/; point here to check against it.
EVIDENCE_ROOT = Path(os.environ.get('MIXPI_EVIDENCE_ROOT', ROOT))


def quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return TIMELINE.main(argv)


def embedded(html):
    match = re.search(r'<script id="climb-data" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(match.group(1))


class RealDataTests(unittest.TestCase):
    def setUp(self):
        self.data = TIMELINE.load()

    def test_real_data_is_valid(self):
        self.assertEqual(TIMELINE.validate(self.data), [])
        self.assertEqual(self.data['schemaVersion'], TIMELINE.SCHEMA_VERSION)

    def test_covers_builds_a_to_k_and_rounds_1_to_6(self):
        done = [e['id'] for e in self.data['events'] if e['status'] == 'done']
        for build in 'ABCDEFGHIJK':
            self.assertIn(build, done)
        for round_no in range(1, 7):
            self.assertIn(f'R{round_no}', done)
        pending = {e['id'] for e in self.data['events'] if e['status'] == 'pending'}
        self.assertLessEqual(pending, {'L', 'R7'})

    def test_waves_c1_to_j11_are_present(self):
        ids = {w['id'] for w in self.data['waves']}
        expected = {'C1', 'C2', 'C3', 'D1', 'E1', 'F1', 'G1', 'G2', 'G3', 'H1', 'I1', 'I2', 'I3'}
        expected |= {f'J{n}' for n in range(1, 12)}
        self.assertLessEqual(expected, ids)

    def test_decisions_cover_spec_2a_to_2g_and_plan_12_5_to_12_11(self):
        ids = {d['id'] for d in self.data['decisions']}
        self.assertLessEqual({f'2{c}' for c in 'abcdefg'}, ids)
        self.assertLessEqual({f'12.{n}' for n in range(5, 12)}, ids)

    def test_owner_quotes_appear_verbatim_in_their_source(self):
        """Every quote is the owner's exact words in the cited spec, plan or brief."""
        for decision in self.data['decisions']:
            source = ROOT / decision['source']
            if not source.exists():
                continue  # the build L brief is on the integration branch, not every checkout
            text = source.read_text(encoding='utf-8')
            for item in decision['items']:
                if item['quote']:
                    with self.subTest(decision=decision['id'], quote=item['quote'][:40]):
                        self.assertIn(item['quote'], text)

    def test_seat_scores_match_the_council_reports(self):
        """Each score equals the report's "Score: N/10." line (needs the untracked evidence)."""
        reports = EVIDENCE_ROOT / 'deploy/ui-redesign-20261117/council'
        if not reports.is_dir():
            self.skipTest('council reports not present; set MIXPI_EVIDENCE_ROOT to the main checkout')
        for event in self.data['events']:
            for score in event.get('scores', []):
                report = (EVIDENCE_ROOT / score['report']).read_text(encoding='utf-8')
                line = re.search(r'^Score: (\d+)/10\.', report, re.M)
                with self.subTest(round=event['id'], seat=score['seat']):
                    self.assertIsNotNone(line)
                    self.assertEqual(int(line.group(1)), score['score'])

    def test_evidence_paths_exist_when_the_evidence_is_present(self):
        if not (EVIDENCE_ROOT / 'deploy/ui-redesign-20261117').is_dir():
            self.skipTest('untracked evidence not present; set MIXPI_EVIDENCE_ROOT to the main checkout')
        missing = [p for p in TIMELINE.evidence_paths(self.data) if not (EVIDENCE_ROOT / p).exists()]
        self.assertEqual(missing, [])

    def test_wave_commits_exist_in_this_history(self):
        git = ROOT / '.git'
        if not git.exists():
            self.skipTest('not a git checkout')
        import subprocess
        heads = {e['head'] for e in self.data['events'] if e.get('head')}
        for head in sorted(heads):
            with self.subTest(head=head):
                result = subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', head + '^{commit}'],
                                        capture_output=True)
                self.assertEqual(result.returncode, 0)


class BrokenSampleTests(unittest.TestCase):
    def setUp(self):
        self.data = TIMELINE.load()

    def broken(self, mutate):
        sample = copy.deepcopy(self.data)
        mutate(sample)
        return TIMELINE.validate(sample)

    def event(self, sample, event_id):
        return next(e for e in sample['events'] if e['id'] == event_id)

    def assertRejected(self, mutate, fragment):
        problems = self.broken(mutate)
        self.assertTrue(any(fragment in p for p in problems), problems)

    def test_wrong_schema_version(self):
        self.assertRejected(lambda d: d.__setitem__('schemaVersion', 2), 'schemaVersion')

    def test_missing_top_level_list(self):
        self.assertRejected(lambda d: d.pop('findings'), 'missing required field "findings"')

    def test_duplicate_ids(self):
        self.assertRejected(lambda d: d['waves'].append(copy.deepcopy(d['waves'][0])), 'duplicate id')
        self.assertRejected(lambda d: d['findings'].append(copy.deepcopy(d['findings'][3])), 'duplicate id')

    def test_unknown_references(self):
        self.assertRejected(lambda d: d['findings'][1]['status'].__setitem__('wave', 'Z9'), 'unknown wave "Z9"')
        self.assertRejected(lambda d: d['findings'][1].__setitem__('found', {'event': 'R99', 'by': 'council'}), 'unknown event "R99"')
        self.assertRejected(lambda d: d['waves'][0].__setitem__('after', 'nope'), 'unknown event "nope"')
        self.assertRejected(lambda d: self.event(d, 'R2').__setitem__('build', 'Q'), 'unknown event "Q"')
        self.assertRejected(lambda d: d['decisions'][0].__setitem__('after', 'R42'), 'unknown event "R42"')
        self.assertRejected(lambda d: self.event(d, 'R1')['scores'][0].__setitem__('seat', 'gemini'), 'unknown seat "gemini"')

    def test_scores_out_of_range(self):
        self.assertRejected(lambda d: self.event(d, 'R1')['scores'][0].__setitem__('score', 11), 'from 1 to 10')
        self.assertRejected(lambda d: self.event(d, 'R1')['scores'][0].__setitem__('score', 0), 'from 1 to 10')
        self.assertRejected(lambda d: self.event(d, 'R1')['scores'][0].__setitem__('score', 7.5), 'from 1 to 10')
        self.assertRejected(lambda d: self.event(d, 'R3')['scores'][2].__setitem__('uncapped', 12), 'from 1 to 10')

    def test_score_rules(self):
        self.assertRejected(lambda d: self.event(d, 'R2')['scores'].pop(), 'one score per seat')
        self.assertRejected(lambda d: self.event(d, 'R1')['scores'][0].__setitem__('uncapped', 9), 'needs a cap')
        self.assertRejected(lambda d: self.event(d, 'R3')['scores'][2].__setitem__('score', 8), 'above its cap')

    def test_dates_must_be_in_order(self):
        self.assertRejected(lambda d: self.event(d, 'K').__setitem__('date', '2026-11-16'), 'time order')
        self.assertRejected(lambda d: self.event(d, 'C').__setitem__('date', '18 Nov'), 'YYYY-MM-DD')
        self.assertRejected(lambda d: self.event(d, 'C').__setitem__('date', None), 'needs a date')

    def test_finding_status_rules(self):
        def fixed_without_wave(d):
            d['findings'][1]['status'] = {'state': 'fixed'}
        self.assertRejected(fixed_without_wave, 'needs "status.wave"')
        def accepted_without_decision(d):
            d['findings'][1]['status'] = {'state': 'owner-accepted'}
        self.assertRejected(accepted_without_decision, 'needs "status.decision"')
        self.assertRejected(lambda d: d['findings'][1]['status'].__setitem__('state', 'done'), 'status.state')
        self.assertRejected(lambda d: d['findings'][1].__setitem__('severity', 'huge'), 'severity')
        self.assertRejected(lambda d: d['findings'][1]['status'].__setitem__('wave', 'J2'), 'reverted wave')

    def test_wave_rules(self):
        self.assertRejected(lambda d: d['waves'][1].__setitem__('shippedIn', 'B'), 'before it was started')
        self.assertRejected(lambda d: d['waves'][1].__setitem__('shippedIn', 'R2'), 'is not a build')
        self.assertRejected(lambda d: d['waves'][1]['commits'].append('not-a-sha'), 'not a commit hash')
        self.assertRejected(lambda d: d['waves'][1]['patches'].append('stage3/x.patch'), '.patch file name')

    def test_acceptance_counts_must_add_up(self):
        self.assertRejected(lambda d: self.event(d, 'C')['acceptance'].__setitem__('pass', 44), 'must equal checks')
        self.assertRejected(lambda d: self.event(d, 'D').__setitem__('gate', None), 'needs "gate"')

    def test_paths_privacy_and_offline(self):
        self.assertRejected(lambda d: d['findings'][0]['evidence'].append('../secret.txt'), 'repo-relative')
        self.assertRejected(lambda d: d['findings'][0]['evidence'].append('/etc/passwd'), 'repo-relative')
        self.assertRejected(lambda d: d['project'].__setitem__('summary', 'see https://example.org'), 'URL')
        self.assertRejected(lambda d: d['project'].__setitem__('summary', 'mail owner@example.org'), 'email')
        self.assertRejected(lambda d: d['project'].__setitem__('summary', '/Users/someone/Music'), 'home path')

    def test_cli_rejects_a_broken_file_and_writes_nothing(self):
        sample = copy.deepcopy(self.data)
        sample['events'][2]['scores'][0]['score'] = 42
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / 'climb.json'
            data.write_text(json.dumps(sample))
            output = Path(folder) / 'out.html'
            self.assertEqual(quiet_main(['--data', str(data), '--output', str(output)]), 1)
            self.assertFalse(output.exists())
            data.write_text('{not json')
            self.assertEqual(quiet_main(['--data', str(data), '--output', str(output), '--check']), 1)

    def test_a_pending_round_7_can_be_completed_by_editing_the_data(self):
        def finish(d):
            build = self.event(d, 'L')
            build.update({'date': '2026-11-22', 'status': 'done', 'head': '90c7709', 'kit': 'deploy/test-image-20261122l/BUILD.md',
                          'gate': {'native': {'passed': 335, 'total': 335, 'skips': 0, 'at': '90c7709', 'log': None},
                                   'mac': {'run': 890, 'result': 'OK', 'skips': 175, 'at': '90c7709'}, 'note': None},
                          'acceptance': {'checks': 5, 'pass': 5, 'fail': 0, 'blocked': 0,
                                         'path': 'deploy/ui-redesign-20261117/acceptance-L/ACCEPTANCE.md', 'note': None}})
            round7 = self.event(d, 'R7')
            round7.update({'date': '2026-11-22', 'status': 'done', 'head': '90c7709', 'scores': [
                {'seat': seat['id'], 'score': 9, 'uncapped': None, 'cap': None, 'report': f'r7-{seat["id"]}.md', 'blockers': [],
                 'standIn': {'model': 'Claude Opus 5.5 xhigh', 'replaced': 'GPT-6.1 Sol xhigh', 'reason': 'Codex not signed in'}
                 if seat['id'] == 'sol' else None}
                for seat in d['seats']]})
        self.assertEqual(self.broken(finish), [])


class HtmlTests(unittest.TestCase):
    def setUp(self):
        self.data = TIMELINE.load()
        self.html = TIMELINE.render(self.data)

    def test_embeds_the_data_exactly(self):
        self.assertNotIn(TIMELINE.PLACEHOLDER, self.html)
        self.assertEqual(embedded(self.html), self.data)

    def test_no_external_urls_or_network_loads(self):
        self.assertIsNone(re.search(r'\b(?:https?|ftp|wss?)://', self.html, re.I))
        self.assertNotIn('//cdn', self.html)
        self.assertIsNone(re.search(r'<(?:script|img|link|iframe)[^>]+(?:src|href)="//', self.html))
        self.assertNotIn('@import', self.html)
        self.assertNotIn('fetch(', self.html)
        self.assertNotIn('XMLHttpRequest', self.html)

    def test_embedded_data_cannot_close_the_script_element(self):
        sample = copy.deepcopy(self.data)
        sample['project']['summary'] = '</script><script>alert(1)</script>'
        html = TIMELINE.render(sample)
        self.assertEqual(html.count('</script>'), self.html.count('</script>'))
        self.assertEqual(embedded(html)['project']['summary'], sample['project']['summary'])

    def test_page_has_the_views_and_json_tools(self):
        for marker in ('id="timeline"', 'id="scores"', 'id="findings"', 'id="waves"', 'id="decisions"',
                       'type="file" id="load"', 'id="download"', 'prefers-color-scheme: dark',
                       ':root[data-theme="dark"]', 'name="viewport"', '<title>Climb Timeline</title>'):
            self.assertIn(marker, self.html)
        # Evidence images resolve from the repo root and fall back to text when absent.
        self.assertIn("var DEFAULT_BASE = '../../';", self.html)
        self.assertIn("addEventListener('error'", self.html)

    def test_committed_page_is_up_to_date(self):
        built = (ROOT / 'tools/climb-timeline/climb-timeline.html').read_text(encoding='utf-8')
        self.assertEqual(built, self.html, 'Rebuild: python3 tools/climb-timeline/build.py')

    def test_template_has_one_placeholder(self):
        with self.assertRaises(TIMELINE.ClimbError):
            TIMELINE.render(self.data, template='<html></html>')

    def test_build_writes_the_page(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'page.html'
            self.assertEqual(quiet_main(['--output', str(output)]), 0)
            self.assertEqual(output.read_text(encoding='utf-8'), self.html)
            self.assertFalse(output.with_suffix('.html.tmp').exists())


if __name__ == '__main__':
    unittest.main()
