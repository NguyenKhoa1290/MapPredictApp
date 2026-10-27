import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import auto_deploy


class DeploymentGateTests(unittest.TestCase):
    def test_requires_matching_verified_main(self):
        main, old = 'a' * 40, 'b' * 40
        for marker in (None, old):
            refs = {'refs/heads/main': main, 'refs/heads/deploy-ready': marker}
            self.assertIsNone(auto_deploy.eligible_revision(refs, None))
        self.assertEqual(auto_deploy.eligible_revision({
            'refs/heads/main': main, 'refs/heads/deploy-ready': main}, old), main)

    def test_already_deployed_or_invalid_ref_is_ignored(self):
        main = 'a' * 40
        self.assertIsNone(auto_deploy.eligible_revision({
            'refs/heads/main': main, 'refs/heads/deploy-ready': main}, main))
        self.assertIsNone(auto_deploy.eligible_revision({
            'refs/heads/main': '--bad', 'refs/heads/deploy-ready': '--bad'}, None))

    def test_local_edits_prevent_fetch_and_deployment(self):
        with patch.object(auto_deploy, 'command', side_effect=[auto_deploy.EXPECTED_REMOTE, 'main', ' M app.py']) as run:
            self.assertFalse(auto_deploy.check_once())
            self.assertEqual(run.call_count, 3)

    def test_wrong_remote_or_branch_is_rejected(self):
        for outputs in (['https://example.com/wrong.git'], [auto_deploy.EXPECTED_REMOTE, 'feature']):
            with patch.object(auto_deploy, 'command', side_effect=outputs):
                with self.assertRaises(RuntimeError):
                    auto_deploy.check_once()

    def test_deploys_exact_verified_commit_and_checks_record(self):
        revision = 'a' * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.secrets').mkdir()
            state = root / '.secrets' / 'deployment-state.json'
            state.write_text(json.dumps({'active': 'blue', 'revision': 'b' * 40}))
            calls = []

            def run(*args, **kwargs):
                calls.append(args)
                if args[:3] == ('git', 'remote', 'get-url'):
                    return auto_deploy.EXPECTED_REMOTE
                if args[:2] == ('git', 'branch'):
                    return 'main'
                if args[:2] == ('git', 'ls-remote'):
                    return f'{revision}\trefs/heads/main\n{revision}\trefs/heads/deploy-ready'
                if args[:2] == ('git', 'rev-parse'):
                    return revision
                if args[-1] == 'deploy':
                    state.write_text(json.dumps({'active': 'green', 'revision': revision}))
                return ''

            with patch.object(auto_deploy, 'ROOT', root), patch.object(auto_deploy, 'command', side_effect=run):
                self.assertTrue(auto_deploy.check_once())
            self.assertIn(('git', 'merge', '--ff-only', revision), calls)
            self.assertNotIn('-Pull', calls[-1])

    def test_failed_deployment_never_records_success(self):
        revision = 'a' * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.secrets').mkdir()
            state = root / '.secrets' / 'deployment-state.json'
            initial = json.dumps({'active': 'blue', 'revision': 'b' * 40})
            state.write_text(initial)
            responses = [auto_deploy.EXPECTED_REMOTE, 'main', '',
                         f'{revision} refs/heads/main\n{revision} refs/heads/deploy-ready',
                         '', '', '', '', '', revision, RuntimeError('Build failed')]
            with patch.object(auto_deploy, 'ROOT', root), patch.object(auto_deploy, 'command', side_effect=responses):
                with self.assertRaisesRegex(RuntimeError, 'Build failed'):
                    auto_deploy.check_once()
            self.assertEqual(state.read_text(), initial)


if __name__ == '__main__':
    unittest.main()
