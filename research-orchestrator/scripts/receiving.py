#!/usr/bin/env python3
"""Check a declared delivery once; rejected science can be a valid exception package."""

import codecs
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

from coord import CoordError, Parser, json_text, load_json, write_output


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def below(root, raw):
    if not isinstance(raw, str) or not raw.strip() or '..' in Path(raw).parts:
        raise ValueError('invalid path or parent traversal')
    path = (root / raw).resolve()
    path.relative_to(root)
    if not path.is_file():
        raise ValueError('missing regular file')
    return path


def valid_sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F]{64}', value) is not None


def text_identity(path):
    """CRLF->LF only; retain BOM, bare CR, spaces, raw SHA, and all other bytes."""
    value = hashlib.sha256()
    decoder = codecs.getincrementaldecoder('utf-8')('strict')
    carry = b''
    size = 0
    with path.open('rb') as handle:
        for raw in iter(lambda: handle.read(1024 * 1024), b''):
            decoder.decode(raw)
            block = carry + raw
            carry = b'\r' if block.endswith(b'\r') else b''
            if carry:
                block = block[:-1]
            block = block.replace(b'\r\n', b'\n')
            value.update(block)
            size += len(block)
    decoder.decode(b'', final=True)
    value.update(carry)
    return {'sha256_crlf_to_lf': value.hexdigest(), 'normalized_bytes': size + len(carry)}


def pointer(value, address):
    if address == '':
        return value
    if not isinstance(address, str) or not address.startswith('/'):
        raise ValueError('JSON pointer must begin with /')
    for part in address[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def cycle(value):
    if type(value) is int:
        return value
    if isinstance(value, str):
        match = re.fullmatch(r'(?:FIX)?(\d+)', value.strip().upper())
        if match:
            return int(match.group(1))
    raise ValueError('not a declared review-cycle value')


def support_manifest(directory):
    """Map declared support references, never infer a report by globbing round names."""
    receipt_path = directory / 'AUTHOR_RESULT.json'
    receipt = load_json(receipt_path)
    declared = receipt.get('artifacts')
    if not isinstance(declared, list):
        raise CoordError('support receipt artifacts must be a list')
    entries = []
    by_path = {}
    for item in declared:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str):
            raise CoordError('invalid declared support artifact')
        entry = {'id': item.get('relative_path') or item['path'], 'path': item['path'],
                 'sha256': item.get('sha256'), 'owner': 'support', 'role': 'artifact'}
        entries.append(entry)
        by_path[os.path.normcase(str((directory / item['path']).resolve()))] = entry
    review = receipt.get('review', {})
    candidates = []
    if isinstance(review, dict):
        if isinstance(review.get('report_ref'), str):
            candidates.append({'path': review['report_ref']})
        for key, value in review.items():
            if 'report' in key.lower() and isinstance(value, dict):
                declared_path = value.get('path') or value.get('relative_path')
                if isinstance(declared_path, str):
                    candidates.append(dict(value, path=declared_path))
    unique = {os.path.normcase(str((directory / c['path']).resolve())): c for c in candidates}
    if len(unique) != 1:
        raise CoordError('support receipt needs one explicit original review reference; use --manifest for other layouts')
    key, ref = next(iter(unique.items()))
    if key not in by_path:
        raise CoordError('original review must be a declared, hashed artifact')
    report = by_path[key]
    if ref.get('sha256') is not None and ref['sha256'] != report.get('sha256'):
        raise CoordError('original review reference and artifact list disagree on raw SHA256')
    report['role'] = 'review_report'
    report['owner'] = 'reviewer'
    manifest = {'schema_version': 1, 'task_id': receipt.get('task_id'), 'artifacts': entries,
                'review': {'artifact': report['id'], 'verdict_pointer': '/verdict',
                           'accepted_scope_pointer': '/accepted_scope'}, 'bindings': [],
                'reported_work_status': receipt.get('work_status') or receipt.get('status'),
                'reported_concerns': receipt.get('concerns', []),
                'receipt_source': str(receipt_path), 'receipt_sha256': digest(receipt_path)}
    runtime = next((e for e in entries if Path(e['path']).name == 'RUNTIME_PROOF.json'), None)
    if runtime:
        manifest['bindings'].append({'label': 'report bound to captured runtime proof',
            'left': {'artifact': report['id'], 'pointer': '@sha256'},
            'right': {'artifact': runtime['id'], 'pointer': '/report_sha256'}})
        raw_runtime = load_json(below(directory, runtime['path']))
        scope_ids = raw_runtime.get('original_scope_ids')
        if isinstance(scope_ids, list):
            manifest['coverage'] = {'report_artifact': report['id'], 'pointer': '/coverage',
                                    'id_key': 'scope_id', 'original_scope_ids': scope_ids}
    return manifest, receipt_path


def check(manifest, root, previous=None):
    if not isinstance(manifest.get('task_id'), str) or not manifest['task_id'].strip():
        raise CoordError('task_id must be nonempty')
    artifacts = manifest.get('artifacts')
    if not isinstance(artifacts, list) or not artifacts:
        raise CoordError('artifacts must contain actual declared delivery evidence')
    checked, paths, data = {}, {}, {}
    issues, warnings = [], []
    protected = []
    for entry in artifacts:
        label = entry.get('id') if isinstance(entry, dict) else None
        owner = entry.get('owner', 'support') if isinstance(entry, dict) else 'support'
        try:
            if not isinstance(label, str) or not label or label in checked:
                raise ValueError('artifact ID missing or duplicated')
            if not valid_sha(entry.get('sha256')):
                raise ValueError('missing valid expected SHA256')
            path = below(root, entry['path'])
            protected.append(path)
            actual = digest(path)
            if actual != entry['sha256'].lower():
                raise ValueError('raw SHA256 mismatch')
            record = {'path': str(path), 'sha256': actual, 'bytes': path.stat().st_size,
                      'role': entry.get('role', 'artifact'), 'owner': owner}
            checked[label], paths[label] = record, path
            bridge = entry.get('transport')
            if bridge:
                if record['role'] not in ('metadata', 'transport'):
                    raise ValueError('text transport bridges are forbidden for science/data/report artifacts')
                if bridge.get('rule') != 'utf8_crlf_lf' or not valid_sha(bridge.get('counterpart_sha256')):
                    raise ValueError('transport counterpart needs an explicit rule and raw SHA256')
                counterpart = below(root, bridge['counterpart_path'])
                protected.append(counterpart)
                other_sha = digest(counterpart)
                if other_sha != bridge['counterpart_sha256'].lower():
                    raise ValueError('counterpart raw SHA256 mismatch')
                a, b = text_identity(path), text_identity(counterpart)
                if a != b:
                    raise ValueError('transport differs beyond CRLF/LF')
                record['transport_relation'] = {'counterpart_path': str(counterpart),
                    'counterpart_sha256': other_sha, 'rule': bridge['rule'],
                    'normalized_identity': a, 'originals_written': False}
        except (KeyError, TypeError, ValueError, OSError, UnicodeError) as exc:
            issues.append({'artifact': label, 'owner': owner, 'issue': str(exc)})

    def value(ref):
        key = ref['artifact']
        if key not in checked:
            raise ValueError('unverified referenced artifact ' + str(key))
        if ref.get('pointer') == '@sha256':
            return checked[key]['sha256']
        if key not in data:
            data[key] = load_json(paths[key])
        return pointer(data[key], ref.get('pointer', ''))

    bindings = manifest.get('bindings', [])
    if not isinstance(bindings, list):
        raise CoordError('bindings must be a list')
    bound = []
    for b in bindings:
        try:
            left, right = value(b['left']), value(b['right'])
            kind = b.get('kind', 'exact')
            if kind not in ('exact', 'review_cycle'):
                raise ValueError('unknown binding kind')
            match = cycle(left) == cycle(right) if kind == 'review_cycle' else left == right
            bound.append({'label': b.get('label'), 'kind': kind, 'left': left, 'right': right, 'matched': match})
            if not match:
                raise ValueError('binding mismatch')
        except (KeyError, IndexError, TypeError, ValueError, CoordError) as exc:
            issues.append({'binding': b.get('label') if isinstance(b, dict) else None,
                           'owner': 'support', 'issue': str(exc)})
    review_record = None
    if manifest.get('review'):
        try:
            spec = manifest['review']
            verdict = value({'artifact': spec['artifact'], 'pointer': spec.get('verdict_pointer', '/verdict')})
            scopes = value({'artifact': spec['artifact'], 'pointer': spec.get('accepted_scope_pointer', '/accepted_scope')})
            if not isinstance(verdict, str) or not isinstance(scopes, list) or any(not isinstance(x, str) for x in scopes):
                raise ValueError('invalid original verdict or accepted_scope')
            review_record = {'verdict': verdict, 'accepted_scope': scopes, 'report_ref': checked[spec['artifact']],
                             'source_independence': 'not_certified_by_this_tool'}
            if verdict.upper() in ('BLOCK', 'REJECT', 'REJECTED', 'FAILED') and scopes:
                warnings.append('original refusal declares nonempty accepted_scope; receiver must resolve original semantics')
        except (KeyError, IndexError, TypeError, ValueError, CoordError) as exc:
            issues.append({'owner': 'reviewer', 'issue': 'original review reference: ' + str(exc)})
    coverage = manifest.get('coverage')
    if coverage:
        try:
            rows = value({'artifact': coverage['report_artifact'], 'pointer': coverage['pointer']})
            expected = coverage['original_scope_ids']
            if not isinstance(rows, list) or not isinstance(expected, list):
                raise ValueError('coverage and original scope IDs must be lists')
            ids = [r[coverage.get('id_key', 'scope_id')] for r in rows]
            if len(ids) != len(set(ids)) or set(ids) != set(expected):
                raise ValueError('original scope coverage missing, duplicated, or changed')
        except (KeyError, TypeError, ValueError, CoordError) as exc:
            issues.append({'owner': 'reviewer', 'issue': 'coverage structure: ' + str(exc)})
    compatible = previous is not None and previous.get('task_id') == manifest['task_id']
    prior = previous.get('artifact_identity', {}) if compatible else {}
    changes = {'baseline_compatible': compatible,
               'new': sorted(k for k in checked if k not in prior),
               'changed': sorted(k for k in checked if k in prior and checked[k] != prior[k]),
               'removed': sorted(k for k in prior if k not in checked)}
    refused = review_record is not None and review_record['verdict'].upper() in ('BLOCK', 'REJECT', 'REJECTED', 'FAILED')
    result = {'schema_version': 1, 'command': 'receive', 'ok': not issues,
              'task_id': manifest['task_id'], 'package_status': 'NEEDS_OWNER_METADATA' if issues else 'READY',
              'package_kind': 'reviewed_exception' if refused else 'reviewed_result' if review_record else 'metadata_delivery',
              'artifact_identity': checked, 'bindings': bound, 'review_record': review_record,
              'issues': issues, 'warnings': warnings, 'changes': changes,
              'reported_work_status': manifest.get('reported_work_status'),
              'reported_concerns': manifest.get('reported_concerns', []),
              'science_acceptance': 'not_decided', 'objective_complete': False,
              'automatic_dispatch_or_state_mutation': False,
              'decision_summary': {'identity': 'owner_correction_needed' if issues else 'declared_files_matched',
                  'original_scientific_verdict': review_record['verdict'] if review_record else 'not_supplied',
                  'accepted_scope_from_original_report': review_record['accepted_scope'] if review_record else [],
                  'owner_routes': sorted(set(i['owner'] for i in issues)),
                  'scope': 'package reception only; original source/independence/science judgment remains with its receiver'}}
    return result, protected


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = Parser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--manifest')
    mode.add_argument('--support-dir')
    parser.add_argument('--root')
    parser.add_argument('--receipt-sha', help='caller-attested support receipt SHA, optional')
    parser.add_argument('--previous')
    parser.add_argument('--output')
    try:
        args = parser.parse_args(argv)
        if args.support_dir:
            root = Path(args.support_dir).resolve(strict=True)
            manifest, source = support_manifest(root)
            if args.receipt_sha and (not valid_sha(args.receipt_sha) or manifest['receipt_sha256'] != args.receipt_sha.lower()):
                raise CoordError('caller-attested support receipt SHA mismatch')
        else:
            source = Path(args.manifest).resolve(strict=True)
            manifest = load_json(source)
            root = Path(args.root).resolve(strict=True) if args.root else source.parent
        previous = load_json(args.previous) if args.previous else None
        result, protected = check(manifest, root, previous)
        result['source_manifest'] = {'path': str(source), 'sha256': digest(source),
                                     'caller_attested_receipt': bool(args.support_dir and args.receipt_sha)}
        protected.append(source)
        if args.previous:
            protected.append(args.previous)
        if args.output:
            write_output(args.output, json_text(result), protected)
        sys.stdout.write(json_text(result))
        return 0 if result['ok'] else 2
    except (CoordError, OSError, ValueError, RuntimeError, TypeError) as exc:
        errors = exc.errors if isinstance(exc, CoordError) else [str(exc)]
        sys.stdout.write(json_text({'command': 'receive', 'ok': False, 'errors': errors,
                                   'science_acceptance': 'not_decided', 'objective_complete': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
