#!/usr/bin/env python3
"""Validate climb.json and build one standalone climb-timeline.html (no server, no network)."""

import argparse
import datetime
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = HERE / 'climb.json'
TEMPLATE = HERE / 'timeline.source.html'
OUTPUT = HERE / 'climb-timeline.html'
PLACEHOLDER = '__CLIMB_JSON__'
SCHEMA_VERSION = 1

EVENT_KINDS = ('build', 'council', 'session')
EVENT_STATUS = ('done', 'pending')
WAVE_STATUS = ('shipped', 'reverted', 'pending')
SEVERITIES = ('critical', 'major', 'minor', 'info')
FINDING_STATES = ('fixed', 'pending', 'owner-accepted', 'listed', 'open', 'closed')
FOUND_BY = ('acceptance', 'council', 'conformance', 'preview', 'builder', 'owner', 'session')
DECISION_KINDS = ('spec', 'plan', 'brief')
COMMIT = re.compile(r'^[0-9a-f]{7,40}$')
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')


class ClimbError(ValueError):
    """climb.json does not match the schema; the message lists every problem."""


def _date(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError
    return datetime.date.fromisoformat(value)


def _rel_path(value):
    """Evidence and doc paths are repo-root relative, with no URL, parent hop or absolute root."""
    return (isinstance(value, str) and value and not value.startswith(('/', '~'))
            and '://' not in value and '\\' not in value
            and '..' not in Path(value).parts)


def validate(data):
    """Return the list of problems in a parsed climb.json; empty means valid."""
    problems = []

    def need(obj, where, fields):
        if not isinstance(obj, dict):
            problems.append(f'{where}: must be an object')
            return False
        missing = [name for name in fields if name not in obj]
        for name in missing:
            problems.append(f'{where}: missing required field "{name}"')
        return not missing

    def path_ok(value, where):
        if value is not None and not _rel_path(value):
            problems.append(f'{where}: "{value}" must be a repo-relative path (no URL, "..", or leading /)')

    if not need(data, 'root', ('schemaVersion', 'project', 'seats', 'events', 'waves', 'findings', 'decisions')):
        return problems
    if data['schemaVersion'] != SCHEMA_VERSION:
        problems.append(f'root: schemaVersion must be {SCHEMA_VERSION}, got {data["schemaVersion"]!r}')
    for name in ('seats', 'events', 'waves', 'findings', 'decisions'):
        if not isinstance(data[name], list):
            problems.append(f'root: "{name}" must be a list')
            return problems
    if need(data['project'], 'project', ('title', 'updated', 'target')):
        target = data['project']['target']
        if not (isinstance(target, int) and 1 <= target <= 10):
            problems.append('project.target: must be an integer from 1 to 10')
        for i, source in enumerate(data['project'].get('sources', [])):
            if need(source, f'project.sources[{i}]', ('label', 'path')):
                path_ok(source['path'], f'project.sources[{i}].path')

    def unique(items, kind):
        ids = {}
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item.get('id'):
                problems.append(f'{kind}[{i}]: needs a non-empty string "id"')
                continue
            if item['id'] in ids:
                problems.append(f'{kind}: duplicate id "{item["id"]}"')
            ids[item['id']] = item
        return ids

    seats = unique(data['seats'], 'seats')
    events = unique(data['events'], 'events')
    waves = unique(data['waves'], 'waves')
    findings = unique(data['findings'], 'findings')
    decisions = unique(data['decisions'], 'decisions')
    order = {event_id: i for i, event_id in enumerate(events)}

    def ref(value, table, kind, where, nullable=False):
        if value is None and nullable:
            return
        if value not in table:
            problems.append(f'{where}: unknown {kind} "{value}"')

    def score_ok(value, where, nullable=False):
        if value is None and nullable:
            return
        if not (isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 10):
            problems.append(f'{where}: score must be an integer from 1 to 10, got {value!r}')

    def commits_ok(values, where):
        if not isinstance(values, list):
            problems.append(f'{where}: must be a list')
            return
        for value in values:
            if not (isinstance(value, str) and COMMIT.match(value)):
                problems.append(f'{where}: "{value}" is not a commit hash')

    # Events: kinds, dates in time order, builds and council rounds.
    last_date, last_id = None, None
    for event_id, event in events.items():
        where = f'event {event_id}'
        if not need(event, where, ('kind', 'title', 'date', 'status', 'summary', 'evidence')):
            continue
        if event['kind'] not in EVENT_KINDS:
            problems.append(f'{where}: kind must be one of {EVENT_KINDS}')
        if event['status'] not in EVENT_STATUS:
            problems.append(f'{where}: status must be one of {EVENT_STATUS}')
        try:
            day = _date(event['date'])
        except (TypeError, ValueError):
            problems.append(f'{where}: date must be YYYY-MM-DD or null')
            day = None
        if day is None and event['status'] == 'done':
            problems.append(f'{where}: a done event needs a date')
        if day is not None:
            if last_date is not None and day < last_date:
                problems.append(f'{where}: date {day} is before {last_id} ({last_date}); events must be in time order')
            last_date, last_id = day, event_id
        if event.get('head') is not None:
            commits_ok([event['head']], f'{where}.head')
        evidence = event['evidence']
        if need(evidence, f'{where}.evidence', ('pairs', 'shots', 'docs')):
            for key in ('pairs', 'shots', 'docs'):
                for value in evidence[key]:
                    path_ok(value, f'{where}.evidence.{key}')
            for value in evidence['pairs']:
                if isinstance(value, str) and not value.endswith('.png'):
                    problems.append(f'{where}.evidence.pairs: "{value}" must be a .png')
        if event['kind'] == 'build':
            if not need(event, where, ('head', 'pigenRuns', 'patches', 'kit', 'gate', 'acceptance')):
                continue
            path_ok(event['kit'], f'{where}.kit')
            runs = event['pigenRuns']
            if not (isinstance(runs, list) and runs and all(isinstance(r, int) and r > 0 for r in runs)):
                problems.append(f'{where}.pigenRuns: must be a non-empty list of positive integers')
            if event['status'] == 'done':
                for name in ('head', 'gate', 'acceptance', 'kit'):
                    if event[name] is None:
                        problems.append(f'{where}: a done build needs "{name}"')
            gate = event['gate']
            if gate is not None and need(gate, f'{where}.gate', ('native', 'mac')):
                native = gate['native']
                if native is not None and need(native, f'{where}.gate.native', ('passed', 'total', 'skips', 'at')):
                    if not all(isinstance(native[k], int) and native[k] >= 0 for k in ('passed', 'total', 'skips')):
                        problems.append(f'{where}.gate.native: passed, total and skips must be counts')
                    elif native['passed'] > native['total']:
                        problems.append(f'{where}.gate.native: passed exceeds total')
                    commits_ok([native['at']], f'{where}.gate.native.at')
                    path_ok(native.get('log'), f'{where}.gate.native.log')
        if event['kind'] in ('build', 'session'):
            acceptance = event.get('acceptance')
            if acceptance is not None and need(acceptance, f'{where}.acceptance', ('checks', 'pass', 'fail', 'blocked', 'path')):
                path_ok(acceptance['path'], f'{where}.acceptance.path')
                counts = [acceptance[k] for k in ('checks', 'pass', 'fail', 'blocked')]
                if all(isinstance(c, int) for c in counts):
                    other = acceptance.get('other', 0)
                    if not isinstance(other, int) or counts[1] + counts[2] + counts[3] + other != counts[0]:
                        problems.append(f'{where}.acceptance: pass + fail + blocked (+ other) must equal checks')
                elif any(c is not None and not isinstance(c, int) for c in counts):
                    problems.append(f'{where}.acceptance: counts must be integers or null')
        if event['kind'] in ('council', 'session') and 'build' in event:
            ref(event['build'], events, 'event', f'{where}.build')
            if event['build'] in order and order[event['build']] > order[event_id]:
                problems.append(f'{where}.build: "{event["build"]}" comes after this event')
        if event['kind'] == 'council':
            if not need(event, where, ('head', 'build', 'scores')):
                continue
            if not isinstance(event['scores'], list):
                problems.append(f'{where}.scores: must be a list')
                continue
            if event['status'] == 'done' and sorted(s.get('seat') for s in event['scores'] if isinstance(s, dict)) != sorted(seats):
                problems.append(f'{where}.scores: a done round needs exactly one score per seat ({", ".join(seats)})')
            for i, score in enumerate(event['scores']):
                swhere = f'{where}.scores[{i}]'
                if not need(score, swhere, ('seat', 'score', 'uncapped', 'cap', 'standIn', 'report', 'blockers')):
                    continue
                ref(score['seat'], seats, 'seat', f'{swhere}.seat')
                score_ok(score['score'], f'{swhere}.score')
                score_ok(score['uncapped'], f'{swhere}.uncapped', nullable=True)
                path_ok(score['report'], f'{swhere}.report')
                cap = score['cap']
                if cap is not None and need(cap, f'{swhere}.cap', ('limit', 'reason')):
                    score_ok(cap['limit'], f'{swhere}.cap.limit')
                    if isinstance(cap['limit'], int) and isinstance(score['score'], int) and score['score'] > cap['limit']:
                        problems.append(f'{swhere}: score is above its cap')
                if score['uncapped'] is not None and cap is None:
                    problems.append(f'{swhere}: an uncapped score needs a cap')
                if score['standIn'] is not None and need(score['standIn'], f'{swhere}.standIn', ('model', 'replaced', 'reason')):
                    pass
                if not isinstance(score['blockers'], list):
                    problems.append(f'{swhere}.blockers: must be a list')

    # Waves: references to events, patches and commits.
    for wave_id, wave in waves.items():
        where = f'wave {wave_id}'
        if not need(wave, where, ('title', 'patches', 'after', 'shippedIn', 'status', 'fixes', 'tests', 'commits')):
            continue
        if wave['status'] not in WAVE_STATUS:
            problems.append(f'{where}: status must be one of {WAVE_STATUS}')
        ref(wave['after'], events, 'event', f'{where}.after')
        ref(wave['shippedIn'], events, 'event', f'{where}.shippedIn', nullable=True)
        if wave['shippedIn'] is not None and events.get(wave['shippedIn'], {}).get('kind') not in (None, 'build'):
            problems.append(f'{where}.shippedIn: "{wave["shippedIn"]}" is not a build')
        if wave['status'] in ('shipped', 'pending') and wave['shippedIn'] is None:
            problems.append(f'{where}: a {wave["status"]} wave needs "shippedIn"')
        if (wave['after'] in order and wave['shippedIn'] in order
                and order[wave['shippedIn']] < order[wave['after']]):
            problems.append(f'{where}: shipped in "{wave["shippedIn"]}" before it was started after "{wave["after"]}"')
        for patch in wave['patches']:
            if not (isinstance(patch, str) and patch.endswith('.patch') and '/' not in patch):
                problems.append(f'{where}.patches: "{patch}" must be a .patch file name')
        commits_ok(wave['commits'], f'{where}.commits')
        path_ok(wave.get('brief'), f'{where}.brief')

    # Findings: where found, status and links.
    for finding_id, finding in findings.items():
        where = f'finding {finding_id}'
        if not need(finding, where, ('title', 'found', 'severity', 'status', 'evidence')):
            continue
        if finding['severity'] not in SEVERITIES:
            problems.append(f'{where}: severity must be one of {SEVERITIES}')
        for i, found in enumerate([finding['found']] + list(finding.get('also', []))):
            fwhere = f'{where}.found' if i == 0 else f'{where}.also[{i - 1}]'
            if need(found, fwhere, ('event', 'by')):
                ref(found['event'], events, 'event', f'{fwhere}.event')
                if found['by'] not in FOUND_BY:
                    problems.append(f'{fwhere}.by: must be one of {FOUND_BY}')
        status = finding['status']
        if need(status, f'{where}.status', ('state',)):
            state = status['state']
            if state not in FINDING_STATES:
                problems.append(f'{where}.status.state: must be one of {FINDING_STATES}')
            if 'wave' in status:
                ref(status['wave'], waves, 'wave', f'{where}.status.wave')
            if 'decision' in status:
                ref(status['decision'], decisions, 'decision', f'{where}.status.decision')
            if state in ('fixed', 'pending') and 'wave' not in status:
                problems.append(f'{where}: a {state} finding needs "status.wave"')
            if state == 'owner-accepted' and 'decision' not in status:
                problems.append(f'{where}: an owner-accepted finding needs "status.decision"')
            if state == 'fixed' and waves.get(status.get('wave'), {}).get('status') == 'reverted':
                problems.append(f'{where}: fixed by a reverted wave')
        if not isinstance(finding['evidence'], list):
            problems.append(f'{where}.evidence: must be a list')
        else:
            for value in finding['evidence']:
                path_ok(value, f'{where}.evidence')

    # Decisions: the owner's words, after a known event.
    for decision_id, decision in decisions.items():
        where = f'decision {decision_id}'
        if not need(decision, where, ('kind', 'title', 'date', 'after', 'source', 'items')):
            continue
        if decision['kind'] not in DECISION_KINDS:
            problems.append(f'{where}: kind must be one of {DECISION_KINDS}')
        ref(decision['after'], events, 'event', f'{where}.after')
        path_ok(decision['source'], f'{where}.source')
        try:
            day = _date(decision['date'])
            after_day = _date(events.get(decision['after'], {}).get('date'))
            if day is not None and after_day is not None and day < after_day:
                problems.append(f'{where}: dated before the event it follows ({decision["after"]})')
        except (TypeError, ValueError):
            problems.append(f'{where}: date must be YYYY-MM-DD')
        if not (isinstance(decision['items'], list) and decision['items']):
            problems.append(f'{where}.items: must be a non-empty list')
        else:
            for i, item in enumerate(decision['items']):
                if need(item, f'{where}.items[{i}]', ('text', 'quote')):
                    if item['quote'] is not None and not (isinstance(item['quote'], str) and item['quote'].strip()):
                        problems.append(f'{where}.items[{i}].quote: must be the owner\'s words or null')

    # Privacy and offline rules for the whole file.
    text = json.dumps(data, ensure_ascii=False)
    if EMAIL.search(text):
        problems.append('privacy: the data contains an email address')
    if '/Users/' in text or '/home/' in text:
        problems.append('privacy: the data contains an absolute home path')
    if re.search(r'\b(?:https?|ftp)://', text, re.I):
        problems.append('offline: the data contains a URL')
    return problems


def load(path=DATA):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise ClimbError(f'{path}: not valid JSON ({error})') from error
    problems = validate(data)
    if problems:
        raise ClimbError('climb.json is invalid:\n  - ' + '\n  - '.join(problems))
    return data


def render(data, template=None):
    template = TEMPLATE.read_text(encoding='utf-8') if template is None else template
    if template.count(PLACEHOLDER) != 1:
        raise ClimbError('Expected exactly one data placeholder in the template')
    encoded = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    encoded = encoded.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    encoded = encoded.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return template.replace(PLACEHOLDER, encoded)


def evidence_paths(data):
    paths = set()
    for event in data['events']:
        for key in ('pairs', 'shots', 'docs'):
            paths.update(event['evidence'][key])
        for score in event.get('scores', []):
            paths.add(score['report'])
        if event.get('acceptance'):
            paths.add(event['acceptance']['path'])
    for finding in data['findings']:
        paths.update(finding['evidence'])
    return sorted(paths)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--evidence-root', type=Path, default=ROOT,
                        help='Folder holding deploy/ (default: this checkout); only used to report missing files')
    parser.add_argument('--check', action='store_true', help='Validate only; write nothing')
    options = parser.parse_args(argv)
    try:
        data = load(options.data)
    except ClimbError as error:
        print(error, file=sys.stderr)
        return 1
    counts = {name: len(data[name]) for name in ('events', 'waves', 'findings', 'decisions')}
    rounds = sum(e['kind'] == 'council' for e in data['events'])
    builds = sum(e['kind'] == 'build' for e in data['events'])
    print(f'climb.json valid: {builds} builds, {rounds} council rounds, {counts["waves"]} waves, '
          f'{counts["findings"]} findings, {counts["decisions"]} decisions')
    missing = [p for p in evidence_paths(data) if not (options.evidence_root / p).exists()]
    if missing:
        print(f'{len(missing)} evidence paths not under {options.evidence_root} '
              '(shown as text in the page): ' + ', '.join(missing[:5]) + (' …' if len(missing) > 5 else ''))
    if options.check:
        return 0
    html = render(data)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = options.output.with_suffix('.html.tmp')
    temporary.write_text(html, encoding='utf-8')
    temporary.replace(options.output)
    print(f'Built {options.output}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
