"""Exercise actual file reception and clock invariants through their CLIs."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def save(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return path

    def artifact(self, name, content, role='metadata'):
        p = self.root / name
        p.write_bytes(content)
        return {'id': name, 'path': name, 'sha256': hashlib.sha256(content).hexdigest(), 'role': role}

    def cli(self, script, *args, ok=True):
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / script)] + [str(x) for x in args],
                                cwd=str(self.root), capture_output=True, encoding='utf-8')
        self.assertEqual(result.stderr, '')
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if ok else 2, data)
        self.assertIs(data['ok'], ok, data)
        return data

    def packet(self):
        report = self.artifact('review.json', json.dumps({'verdict': 'BLOCK', 'revision': 'FIX2',
            'accepted_scope': [], 'coverage': [{'scope_id': 'S1', 'status': 'failed'}]}).encode(), 'review_report')
        request = self.artifact('request.json', b'{"revision":1,"fix_revision":2}')
        return {'task_id': 'A', 'artifacts': [report, request],
                'review': {'artifact': 'review.json'},
                'coverage': {'report_artifact': 'review.json', 'pointer': '/coverage', 'original_scope_ids': ['S1']},
                'bindings': [{'label': 'review cycle, not request freeze revision', 'kind': 'review_cycle',
                              'left': {'artifact': 'request.json', 'pointer': '/fix_revision'},
                              'right': {'artifact': 'review.json', 'pointer': '/revision'}}]}

    def test_rejected_science_is_valid_exception_without_acceptance(self):
        p = self.save('manifest.json', self.packet())
        data = self.cli('receiving.py', '--manifest', p)
        self.assertEqual(data['package_kind'], 'reviewed_exception')
        self.assertEqual(data['review_record']['accepted_scope'], [])
        self.assertEqual(data['science_acceptance'], 'not_decided')
        self.assertFalse(data['objective_complete'])
        self.assertTrue(data['bindings'][0]['matched'])

    def test_true_review_cycle_mismatch_is_not_silently_aliased(self):
        packet = self.packet()
        packet['artifacts'][1] = self.artifact('request.json', b'{"revision":1,"fix_revision":3}')
        data = self.cli('receiving.py', '--manifest', self.save('manifest.json', packet), ok=False)
        self.assertEqual(data['package_status'], 'NEEDS_OWNER_METADATA')
        self.assertFalse(data['bindings'][0]['matched'])

    def test_hash_change_and_scope_loss_are_detected(self):
        packet = self.packet()
        packet['coverage']['original_scope_ids'].append('S2')
        self.cli('receiving.py', '--manifest', self.save('manifest.json', packet), ok=False)
        (self.root / 'review.json').write_bytes(b'changed')
        data = self.cli('receiving.py', '--manifest', self.root / 'manifest.json', ok=False)
        self.assertTrue(any('SHA256' in x['issue'] for x in data['issues']))

    def test_explicit_mixed_newline_bridge_preserves_both_raw_files(self):
        a = self.artifact('wire.txt', b'a\r\nb\nc\r\n')
        b = self.artifact('git.txt', b'a\nb\nc\n')
        a['transport'] = {'counterpart_path': b['path'], 'counterpart_sha256': b['sha256'], 'rule': 'utf8_crlf_lf'}
        before = {p: p.read_bytes() for p in self.root.iterdir()}
        data = self.cli('receiving.py', '--manifest', self.save('manifest.json', {'task_id': 'A', 'artifacts': [a]}))
        self.assertEqual(data['artifact_identity']['wire.txt']['sha256'], a['sha256'])
        self.assertFalse(data['artifact_identity']['wire.txt']['transport_relation']['originals_written'])
        for p, content in before.items():
            self.assertEqual(p.read_bytes(), content)

    def test_bridge_cannot_hide_content_change_or_relax_science_hashes(self):
        a = self.artifact('wire.txt', b'a\r\nb\n')
        b = self.artifact('git.txt', b'a\nc\n')
        a['transport'] = {'counterpart_path': b['path'], 'counterpart_sha256': b['sha256'], 'rule': 'utf8_crlf_lf'}
        self.cli('receiving.py', '--manifest', self.save('m.json', {'task_id': 'A', 'artifacts': [a]}), ok=False)
        b = self.artifact('git.txt', b'a\nb\n')
        a['transport']['counterpart_sha256'] = b['sha256']
        a['role'] = 'science_input'
        self.cli('receiving.py', '--manifest', self.save('m.json', {'task_id': 'A', 'artifacts': [a]}), ok=False)

    def test_output_cannot_overwrite_inputs_and_diff_reports_real_change(self):
        packet = self.packet()
        manifest = self.save('manifest.json', packet)
        self.cli('receiving.py', '--manifest', manifest, '--output', self.root / 'review.json', ok=False)
        previous = self.root / 'previous.json'
        self.cli('receiving.py', '--manifest', manifest, '--output', previous)
        data = self.cli('receiving.py', '--manifest', manifest, '--previous', previous)
        self.assertEqual(data['changes']['changed'], [])
        packet['artifacts'][1] = self.artifact('request.json', b'{"revision":9,"fix_revision":2}')
        self.save('manifest.json', packet)
        data = self.cli('receiving.py', '--manifest', manifest, '--previous', previous)
        self.assertEqual(data['changes']['changed'], ['request.json'])

    def test_legacy_support_receipt_maps_declared_report_without_schema_rewrite(self):
        packet = self.packet()
        runtime = self.artifact('RUNTIME_PROOF.json', json.dumps({'report_sha256': packet['artifacts'][0]['sha256'],
            'original_scope_ids': ['S1']}).encode())
        receipt = {'task_id': 'S', 'status': 'DONE_WITH_CONCERNS', 'artifacts': packet['artifacts'] + [runtime],
                   'review': {'original_verdict': 'BLOCK', 'original_FIX2_report': {
                       'relative_path': 'review.json', 'sha256': packet['artifacts'][0]['sha256']}}}
        source = self.save('AUTHOR_RESULT.json', receipt)
        raw = source.read_bytes()
        data = self.cli('receiving.py', '--support-dir', self.root, '--receipt-sha', hashlib.sha256(raw).hexdigest())
        self.assertEqual(data['package_kind'], 'reviewed_exception')
        self.assertEqual(source.read_bytes(), raw)
        self.cli('receiving.py', '--support-dir', self.root, '--receipt-sha', '0' * 64, ok=False)

    def clock(self, rows):
        return self.save('clock.json', {'observed_at': '2026-10-05T00:00:30Z', 'clocks': rows})

    def span(self, start, end, source='actual-run'):
        return {'start': '2026-10-05T00:00:%02dZ' % start,
                'end': None if end is None else '2026-10-05T00:00:%02dZ' % end, 'source_ref': source}

    def execution(self, spans, **changes):
        row = {'name': 'build', 'kind': 'execution_wall_hard', 'limit_s': 20,
               'intervals': spans, 'intervals_complete': True, 'completeness_source_ref': 'closed-ledger'}
        row.update(changes)
        return row

    def test_execution_union_and_running_wait_count_as_program_wall(self):
        row = self.execution([self.span(0, 10, 'failed-run'), self.span(5, 15)])
        data = self.cli('clock_report.py', '--ledger', self.clock([row]))
        self.assertEqual(data['clocks'][0]['elapsed_s'], 15)
        self.assertEqual(data['clocks'][0]['remaining_s'], 5)
        row['intervals'].append(self.span(15, None, 'running-io-wait'))
        data = self.cli('clock_report.py', '--ledger', self.clock([row]))
        self.assertEqual(data['clocks'][0]['elapsed_s'], 30)
        self.assertEqual(data['clocks'][0]['status'], 'hard_limit_reached')

    def test_partial_ledger_does_not_invent_reliable_balance(self):
        row = self.execution([self.span(0, 10)], intervals_complete=False)
        data = self.cli('clock_report.py', '--ledger', self.clock([row]))
        self.assertIsNone(data['clocks'][0]['elapsed_s'])
        self.assertIsNone(data['clocks'][0]['remaining_s'])
        self.assertEqual(data['clocks'][0]['known_interval_lower_bound_s'], 10)

    def test_legacy_continuous_expiry_preserved_and_soft_milestone_does_not_stop(self):
        base = {'origin': '2026-10-05T00:00:00Z', 'origin_source_ref': 'actual-origin', 'limit_s': 20}
        hard = dict(base, name='old-build', kind='continuous_wall_hard', legacy_contract=True)
        soft = dict(base, name='prepare', kind='milestone_soft')
        data = self.cli('clock_report.py', '--ledger', self.clock([hard, soft]))
        self.assertEqual(data['clocks'][0]['status'], 'hard_limit_reached')
        self.assertEqual(data['clocks'][1]['status'], 'milestone_due_for_assessment')
        self.assertFalse(data['new_budget_or_window_granted'])
        self.assertFalse(data['old_clock_or_cost_reset'])

    def test_coordination_overlap_and_unsourced_time_are_rejected(self):
        run = self.execution([self.span(0, 10)])
        wait = {'name': 'review-wait', 'kind': 'coordination_wait', 'intervals': [self.span(5, 15)],
                'intervals_complete': True, 'completeness_source_ref': 'wait-record'}
        self.cli('clock_report.py', '--ledger', self.clock([run, wait]), ok=False)
        wait['intervals'] = [self.span(10, 20)]
        data = self.cli('clock_report.py', '--ledger', self.clock([run, wait]))
        self.assertEqual(data['clocks'][1]['elapsed_s'], 10)
        wait['intervals'][0]['source_ref'] = None
        self.cli('clock_report.py', '--ledger', self.clock([wait]), ok=False)


    def test_missing_interval_list_cannot_be_inferred_as_zero_elapsed(self):
        ledger = {'observed_at': '2026-10-05T03:00:00Z', 'clocks': [{
            'name': 'partial_execution', 'kind': 'execution_wall_hard', 'limit_s': 1800,
            'intervals_complete': True, 'completeness_source_ref': 'actual-owner-receipt'}]}
        ledger_path = self.save('missing-intervals.json', ledger)
        result = self.cli('clock_report.py', '--ledger', ledger_path)
        self.assertIsNone(result['clocks'][0]['elapsed_s'])
        self.assertIsNone(result['clocks'][0]['remaining_s'])
        self.assertFalse(result['clocks'][0]['account_complete'])


if __name__ == '__main__':
    unittest.main()
