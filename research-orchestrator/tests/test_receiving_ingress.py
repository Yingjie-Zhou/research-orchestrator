import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'receiving_ingress.py'


class IngressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / 'state.json'
        self.packet = self.root / 'packet.json'
        self.original = {'objective_complete': False, 'jobs': [{'accepted_scope': ['old']}],
                         'budget': {'total': 180, 'spent': 26.189255}, 'history': ['failure kept']}
        self.write(self.state, self.original)
        self.write(self.packet, {'command': 'receive', 'ok': True, 'task_id': 'B29_RECEIVING',
            'package_status': 'READY', 'issues': [], 'science_acceptance': 'not_decided',
            'objective_complete': False, 'package_kind': 'reviewed_exception',
            'decision_summary': {'original_scientific_verdict': 'BLOCK'}})

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def run_cli(self, *extras, state_sha=None):
        proc = subprocess.run([sys.executable, '-B', str(SCRIPT), '--state', str(self.state),
            '--packet', str(self.packet), '--expected-state-sha', state_sha or self.digest(self.state),
            '--expected-packet-sha', self.digest(self.packet), *extras], capture_output=True, text=True, encoding='utf-8')
        return proc.returncode, json.loads(proc.stdout)

    def test_preview_is_read_only_and_commit_changes_only_metadata_registry(self):
        before = self.state.read_bytes()
        code, preview = self.run_cli()
        self.assertEqual(code, 0)
        self.assertTrue(preview['would_change'])
        self.assertFalse(preview['committed'])
        self.assertEqual(self.state.read_bytes(), before)
        code, result = self.run_cli('--commit')
        self.assertEqual(code, 0)
        after = json.loads(self.state.read_text())
        self.assertEqual(after.pop('routine_receptions')['B29_RECEIVING']['original_scientific_verdict'], 'BLOCK')
        self.assertEqual(after, self.original)
        self.assertEqual(self.digest(self.state), result['state_after_sha256'])
        self.assertFalse(result['new_budget_or_execution_granted'])

    def test_stale_version_and_lock_contention_preserve_state(self):
        old_sha = self.digest(self.state)
        altered = copy.deepcopy(self.original)
        altered['history'].append('concurrent owner update')
        self.write(self.state, altered)
        before = self.state.read_bytes()
        code, _ = self.run_cli('--commit', state_sha=old_sha)
        self.assertEqual(code, 2)
        self.assertEqual(self.state.read_bytes(), before)
        lock = Path(str(self.state) + '.receiving.lock')
        lock.write_text('other writer')
        code, _ = self.run_cli('--commit')
        self.assertEqual(code, 2)
        self.assertTrue(lock.exists())
        self.assertEqual(self.state.read_bytes(), before)

    def test_repeat_is_idempotent_and_new_identity_cannot_replace_history(self):
        self.assertEqual(self.run_cli('--commit')[0], 0)
        before = self.state.read_bytes()
        code, result = self.run_cli('--commit')
        self.assertEqual(code, 0)
        self.assertFalse(result['changed'])
        self.assertEqual(self.state.read_bytes(), before)
        packet = json.loads(self.packet.read_text())
        packet['unrelated_payload'] = 'new identity'
        self.write(self.packet, packet)
        code, _ = self.run_cli('--commit')
        self.assertEqual(code, 2)
        self.assertEqual(self.state.read_bytes(), before)

    def test_unready_packet_and_output_over_input_do_not_commit(self):
        before = self.state.read_bytes()
        code, _ = self.run_cli('--commit', '--output', str(self.state))
        self.assertEqual(code, 2)
        self.assertEqual(self.state.read_bytes(), before)
        packet = json.loads(self.packet.read_text())
        packet['science_acceptance'] = 'accepted'
        self.write(self.packet, packet)
        code, _ = self.run_cli('--commit')
        self.assertEqual(code, 2)
        self.assertEqual(self.state.read_bytes(), before)

    def test_receipt_write_failure_reports_actual_commit(self):
        output_dir = self.root / 'output-directory'
        output_dir.mkdir()
        code, result = self.run_cli('--commit', '--output', str(output_dir))
        self.assertEqual(code, 2)
        self.assertTrue(result['committed'])
        self.assertIn('routine_receptions', json.loads(self.state.read_text()))


if __name__ == '__main__':
    unittest.main()
