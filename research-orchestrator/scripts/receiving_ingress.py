#!/usr/bin/env python3
"""Register only a metadata reception, with exact state and packet versions.

Preview is the default. Commit is for the existing authorized state owner;
this program does not grant ownership or decide scientific acceptance.
"""
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from coord import CoordError, Parser, json_text, write_output


def sha(data):
    return hashlib.sha256(data).hexdigest()


def proposal(state_path, packet_path, expected_state, expected_packet):
    if state_path == packet_path:
        raise CoordError('state and packet must be separate files')
    state_bytes, packet_bytes = state_path.read_bytes(), packet_path.read_bytes()
    if sha(state_bytes) != expected_state.lower():
        raise CoordError('stale state version: read current state and prepare again')
    if sha(packet_bytes) != expected_packet.lower():
        raise CoordError('packet version does not match the explicit receipt')
    state = json.loads(state_bytes.decode('utf-8-sig'))
    packet = json.loads(packet_bytes.decode('utf-8-sig'))
    if not isinstance(state, dict) or not isinstance(packet, dict):
        raise CoordError('state and packet must be JSON objects')
    if (packet.get('command') != 'receive' or packet.get('ok') is not True
            or packet.get('package_status') != 'READY' or packet.get('issues') != []
            or packet.get('science_acceptance') != 'not_decided'
            or packet.get('objective_complete') is not False):
        raise CoordError('only an identity-ready, science-undecided receiving packet may be registered')
    task_id = packet.get('task_id')
    if not isinstance(task_id, str) or not task_id.strip():
        raise CoordError('packet requires an explicit task_id')
    registry = state.get('routine_receptions', {})
    if not isinstance(registry, dict):
        raise CoordError('existing routine_receptions registry is not an object')
    record = {
        'packet_path': str(packet_path), 'packet_sha256': expected_packet.lower(),
        'package_status': 'READY', 'package_kind': packet.get('package_kind'),
        'science_acceptance': 'not_decided', 'objective_complete': False,
        'source_manifest': packet.get('source_manifest'),
        'original_scientific_verdict': packet.get('decision_summary', {}).get('original_scientific_verdict'),
        'registration_scope': 'metadata reception only; source provenance and scientific decisions remain with their owners',
    }
    # A task ID is immutable once registered; a corrected delivery needs a new
    # explicit reception ID or an owner review, never silent replacement.
    existing = registry.get(task_id)
    if existing is not None and existing != record:
        raise CoordError('task already registered with different reception identity; retain history and resolve with owner')
    candidate = dict(state)
    candidate['routine_receptions'] = dict(registry, **{task_id: record})
    return candidate, task_id, existing is None


def commit(state_path, packet_path, expected_state, expected_packet):
    # Other writers must remain serialized by the existing state owner. This
    # lock coordinates this ingress; it cannot authenticate or lock out arbitrary
    # legacy writers. Rechecking immediately before replace rejects stale data.
    lock = Path(str(state_path) + '.receiving.lock')
    descriptor = None
    temporary = None
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        candidate, task_id, changed = proposal(state_path, packet_path, expected_state, expected_packet)
        if not changed:
            return task_id, False, expected_state.lower()
        encoded = json_text(candidate).encode('utf-8')
        with tempfile.NamedTemporaryFile(dir=state_path.parent, prefix=state_path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if sha(state_path.read_bytes()) != expected_state.lower() or sha(packet_path.read_bytes()) != expected_packet.lower():
            raise CoordError('state or packet changed during registration; nothing committed')
        os.replace(temporary, state_path)
        temporary = None
        return task_id, True, sha(encoded)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if descriptor is not None:
            os.close(descriptor)
            lock.unlink()


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = Parser(description=__doc__)
    parser.add_argument('--state', required=True)
    parser.add_argument('--packet', required=True)
    parser.add_argument('--expected-state-sha', required=True)
    parser.add_argument('--expected-packet-sha', required=True)
    parser.add_argument('--commit', action='store_true', help='existing authorized state owner only')
    parser.add_argument('--output', help='derived operation receipt, never an input path')
    result = None
    try:
        args = parser.parse_args(argv)
        state_path = Path(args.state).resolve(strict=True)
        packet_path = Path(args.packet).resolve(strict=True)
        if args.output and Path(args.output).resolve() in (state_path, packet_path):
            raise CoordError('output cannot overwrite input')
        _, task_id, changed = proposal(state_path, packet_path, args.expected_state_sha, args.expected_packet_sha)
        new_sha = None
        if args.commit:
            task_id, changed, new_sha = commit(state_path, packet_path, args.expected_state_sha, args.expected_packet_sha)
        result = {'command': 'register_reception', 'ok': True, 'task_id': task_id,
                  'committed': args.commit, 'changed': changed if args.commit else False,
                  'would_change': changed if not args.commit else None,
                  'state_before_sha256': args.expected_state_sha.lower(), 'state_after_sha256': new_sha,
                  'packet_sha256': args.expected_packet_sha.lower(),
                  'allowed_state_fields': ['routine_receptions'],
                  'science_acceptance': 'not_decided', 'new_budget_or_execution_granted': False,
                  'owner_authorization_is_external': True,
                  'at_UTC': datetime.now(timezone.utc).isoformat()}
        if args.output:
            write_output(args.output, json_text(result), [state_path, packet_path])
        sys.stdout.write(json_text(result))
        return 0
    except (CoordError, OSError, ValueError, TypeError, RuntimeError) as exc:
        errors = exc.errors if isinstance(exc, CoordError) else [str(exc)]
        failure = dict(result) if result is not None else {
            'command': 'register_reception', 'science_acceptance': 'not_decided',
            'new_budget_or_execution_granted': False}
        failure.update(ok=False, errors=errors)
        sys.stdout.write(json_text(failure))
        return 2


if __name__ == '__main__':
    sys.exit(main())
