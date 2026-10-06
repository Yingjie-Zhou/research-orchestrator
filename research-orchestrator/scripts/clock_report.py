#!/usr/bin/env python3
"""Report declared clock semantics; never reinterpret an old deadline or enforce a budget."""

from datetime import datetime
import math
from pathlib import Path
import sys

from coord import CoordError, Parser, json_text, load_json, write_output


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must have explicit timezone')
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError('timestamp timezone missing')
    return date.timestamp()


def intervals(rows, now):
    if not isinstance(rows, list):
        raise ValueError('intervals must be a list')
    spans = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('source_ref'), str) or not row['source_ref'].strip():
            raise ValueError('each interval needs actual source_ref')
        start = timestamp(row['start'])
        end = now if row.get('end') is None else timestamp(row['end'])
        if start > end or end > now:
            raise ValueError('negative interval or interval beyond observed_at')
        spans.append((start, end))
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def run(data):
    now = timestamp(data['observed_at'])
    rows = data.get('clocks')
    if not isinstance(rows, list):
        raise CoordError('clocks must be a list')
    errors, clocks, names = [], [], set()
    execution_spans = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append('clock must be an object')
            continue
        name = row.get('name')
        try:
            if not isinstance(name, str) or not name or name in names:
                raise ValueError('clock name missing or duplicated')
            names.add(name)
            kind = row.get('kind')
            if kind not in ('execution_wall_hard', 'continuous_wall_hard', 'milestone_soft', 'coordination_wait'):
                raise ValueError('explicit clock kind required')
            cap = row.get('limit_s')
            if cap is not None and (type(cap) not in (int, float) or not math.isfinite(cap) or cap < 0):
                raise ValueError('limit_s must be finite nonnegative or null')
            elapsed, complete = None, False
            spans = []
            if kind in ('execution_wall_hard', 'coordination_wait'):
                if 'intervals' in row:
                    spans = intervals(row['intervals'], now)
                source_ref = row.get('completeness_source_ref')
                complete = ('intervals' in row and row.get('intervals_complete') is True
                            and isinstance(source_ref, str) and bool(source_ref.strip()))
                if complete:
                    elapsed = sum(end - start for start, end in spans)
                if kind == 'execution_wall_hard':
                    execution_spans.extend(spans)
            else:
                origin = row.get('origin')
                if origin is not None:
                    source_ref = row.get('origin_source_ref')
                    if not isinstance(source_ref, str) or not source_ref.strip():
                        raise ValueError('origin needs actual origin_source_ref')
                    elapsed = now - timestamp(origin)
                    if elapsed < 0:
                        raise ValueError('origin after observed_at')
                    complete = True
            if elapsed is None or cap is None:
                status = 'unknown' if elapsed is None else 'recorded_no_limit'
            elif kind == 'milestone_soft':
                status = 'milestone_due_for_assessment' if elapsed >= cap else 'within_soft_milestone'
            else:
                status = 'hard_limit_reached' if kind.endswith('_hard') and elapsed >= cap else 'recorded' if kind == 'coordination_wait' else 'within_declared_hard_limit'
            clocks.append({'name': name, 'kind': kind, 'limit_s': cap, 'elapsed_s': elapsed,
                           'known_interval_lower_bound_s': sum(b-a for a,b in spans) if spans else None,
                           'account_complete': complete, 'status': status,
                           'remaining_s': max(0.0, cap-elapsed) if kind.endswith('_hard') and cap is not None and elapsed is not None else None,
                           'origin': row.get('origin'), 'intervals': row.get('intervals'),
                           'authorization_ref': row.get('authorization_ref'),
                           'legacy_contract': row.get('legacy_contract') is True,
                           'automatic_stop_or_extension': False})
        except (KeyError, TypeError, ValueError) as exc:
            errors.append('{}: {}'.format(name, exc))
    for row in clocks:
        if row['kind'] != 'coordination_wait' or row['intervals'] is None:
            continue
        wait_spans = intervals(row['intervals'], now)
        overlap = sum(max(0, min(b, d)-max(a,c)) for a,b in wait_spans for c,d in execution_spans)
        if overlap:
            errors.append('{}: coordination waiting overlaps running-program intervals; running I/O/waits remain program wall'.format(row['name']))
    return {'schema_version': 1, 'command': 'clock-report', 'ok': not errors,
            'observed_at': data['observed_at'], 'clocks': clocks, 'errors': errors,
            'new_budget_or_window_granted': False, 'old_clock_or_cost_reset': False,
            'science_acceptance': 'not_decided',
            'limits': 'Reports declared records only, no file-mtime origins, no inferred silence or ledger completeness; soft milestones and coordination waits never grant extra hard resources.'}


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = Parser(description=__doc__)
    parser.add_argument('--ledger', required=True)
    parser.add_argument('--output')
    try:
        args = parser.parse_args(argv)
        data = load_json(args.ledger)
        result = run(data)
        if args.output:
            write_output(args.output, json_text(result), [args.ledger])
        sys.stdout.write(json_text(result))
        return 0 if result['ok'] else 2
    except (CoordError, OSError, ValueError, KeyError, TypeError) as exc:
        errors = exc.errors if isinstance(exc, CoordError) else [str(exc)]
        sys.stdout.write(json_text({'command': 'clock-report', 'ok': False, 'errors': errors,
                                   'new_budget_or_window_granted': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
