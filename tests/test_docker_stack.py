import json
from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest.mock import patch

from tools import docker_stack, install_linux


class PortableDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / '.secrets').mkdir()
        (self.root / 'deploy/local/nginx').mkdir(parents=True)
        (self.root / '.env').write_text('MAP_PREDICT_MAX_UPLOAD_BYTES=1000\nMAP_PREDICT_ASSISTANT_ENABLED=0\n')
        (self.root / 'deploy/site.template.conf').write_text('__BACKEND__ __UPLOAD_BYTES__')
        self.config = self.root / 'deploy/local/nginx/active.conf'
        self.config.write_text('app-blue 1000')
        self.state = self.root / '.secrets/deployment-state.json'
        self.state.write_text(json.dumps({'active': 'blue', 'revision': 'b' * 40}))
        self.patcher = patch.object(docker_stack, 'ROOT', self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_candidate_failure_preserves_live_config_and_state(self):
        initial = self.state.read_text()

        def compose(*args, **kwargs):
            if args[:3] == ('exec', '-T', 'app-green'):
                raise RuntimeError('Model failed')
            return ''

        with patch.object(docker_stack, 'run', return_value='a' * 40), \
                patch.object(docker_stack, 'compose', side_effect=compose) as calls:
            with self.assertRaisesRegex(RuntimeError, 'Model failed'):
                docker_stack.deploy()
        self.assertEqual(self.config.read_text(), 'app-blue 1000')
        self.assertEqual(self.state.read_text(), initial)
        self.assertFalse(any(call.args[0] == 'stop' for call in calls.call_args_list))

    def test_proxy_validation_failure_restores_previous_config(self):
        def compose(*args, **kwargs):
            if args == ('exec', '-T', 'app', 'nginx', '-t'):
                raise RuntimeError('Bad proxy')
            return ''

        with patch.object(docker_stack, 'run', return_value='a' * 40), \
                patch.object(docker_stack, 'compose', side_effect=compose):
            with self.assertRaisesRegex(RuntimeError, 'Bad proxy'):
                docker_stack.deploy()
        self.assertEqual(self.config.read_text(), 'app-blue 1000')
        self.assertEqual(json.loads(self.state.read_text())['active'], 'blue')

    def test_switch_records_revision_before_draining_old_slot(self):
        events = []

        def compose(*args, **kwargs):
            events.append(args)
            if args[0] == 'stop':
                state = json.loads(self.state.read_text())
                self.assertEqual(state['active'], 'green')
                self.assertEqual(state['revision'], 'a' * 40)
                self.assertEqual(self.config.read_text(), 'app-green 1000')
            return ''

        with patch.object(docker_stack, 'run', return_value='a' * 40), \
                patch.object(docker_stack, 'compose', side_effect=compose):
            docker_stack.deploy()
        reload_index = events.index(('exec', '-T', 'app', 'nginx', '-s', 'reload'))
        stop_index = events.index(('stop', 'app-blue'))
        self.assertIn(('exec', '-T', 'app', 'ps', '-o', 'args'), events[reload_index + 1:stop_index])
        self.assertEqual(events[-1], ('rm', '-f', 'app-blue'))

    def test_timeout_keeps_previous_container_after_switch(self):
        with patch.object(docker_stack, 'run', return_value='a' * 40), \
                patch.object(docker_stack, 'compose', return_value='') as calls, \
                patch.object(docker_stack, 'wait_for_drain', side_effect=[None, RuntimeError('Still draining')]):
            with self.assertRaisesRegex(RuntimeError, 'Still draining'):
                docker_stack.deploy()
        self.assertEqual(json.loads(self.state.read_text())['active'], 'green')
        self.assertFalse(any(call.args[0] == 'stop' for call in calls.call_args_list))

    def test_start_only_activates_recorded_slot_and_preserves_settings(self):
        with patch.object(docker_stack, 'compose', return_value='') as calls:
            docker_stack.start()
        self.assertEqual(len(calls.call_args_list), 2)
        self.assertEqual(calls.call_args_list[0].args[-1], 'app-blue')
        self.assertEqual(calls.call_args_list[1].args[-2:], ('app', 'cloudflared'))
        self.assertEqual(self.config.read_text(), 'app-blue 1000')

    def test_linux_timer_is_short_lived_and_boot_starts_stack(self):
        units = install_linux.units(PurePosixPath('/srv/map app'), '/usr/bin/python3', 'deploy')
        self.assertIn('OnUnitInactiveSec=5min', units['map-predict-update.timer'])
        self.assertIn('Type=oneshot', units['map-predict-update.service'])
        self.assertIn('"/srv/map app/tools/auto_deploy.py"', units['map-predict-update.service'])
        self.assertIn('WorkingDirectory=/srv/map app\n', units['map-predict-update.service'])
        self.assertIn('Requires=docker.service', units['map-predict-stack.service'])
        self.assertIn('User=deploy', units['map-predict-stack.service'])


if __name__ == '__main__':
    unittest.main()
