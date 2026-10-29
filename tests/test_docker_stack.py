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

    def test_build_failure_does_not_restart_services_or_record_success(self):
        initial = self.state.read_text()
        with patch.object(docker_stack, 'run', return_value='a' * 40), \
                patch.object(docker_stack, 'compose', side_effect=RuntimeError('Build failed')) as calls:
            with self.assertRaisesRegex(RuntimeError, 'Build failed'):
                docker_stack.deploy()
        self.assertEqual(self.state.read_text(), initial)
        self.assertEqual(self.config.read_text(), 'app-blue 1000')
        self.assertEqual(calls.call_count, 1)
        self.assertEqual(calls.call_args.args, ('build', 'web-portal', 'ai-assistant', 'gemini-session'))

    def test_failed_health_check_does_not_record_success(self):
        initial = self.state.read_text()

        def compose(*args, **kwargs):
            if args[0] == 'up' and args[-2:] == ('ai-assistant', 'web-portal'):
                raise RuntimeError('Service unhealthy')
            return ''

        with patch.object(docker_stack, 'run', return_value='a' * 40), \
                patch.object(docker_stack, 'compose', side_effect=compose):
            with self.assertRaisesRegex(RuntimeError, 'Service unhealthy'):
                docker_stack.deploy()
        self.assertEqual(self.state.read_text(), initial)

    def test_success_records_single_mode_only_after_verification(self):
        events = []
        initial = self.state.read_text()

        def compose(*args, **kwargs):
            events.append(args)
            if args[-1] == 'reload':
                self.assertEqual(self.state.read_text(), initial)
                self.assertEqual(self.config.read_text(), 'web-portal 1000')
            return ''

        with patch.object(docker_stack, 'run', return_value='a' * 40), \
                patch.object(docker_stack, 'compose', side_effect=compose):
            docker_stack.deploy()
        state = json.loads(self.state.read_text())
        self.assertEqual(state['mode'], 'single')
        self.assertEqual(state['revision'], 'a' * 40)
        self.assertNotIn('active', state)
        self.assertTrue(any(call[:4] == ('exec', '-T', 'web-portal', 'python') for call in events))
        self.assertFalse(any(call[0] in ('rm', 'stop', 'down') for call in events))
        self.assertFalse(any('ai-embedding' in call for call in events))

    def test_start_uses_one_compose_project_with_dependencies(self):
        with patch.object(docker_stack, 'compose', return_value='') as calls:
            docker_stack.start()
        self.assertEqual(calls.call_args_list[0].args,
                         ('up', '-d', '--build', '--wait', '--wait-timeout', '180'))
        self.assertEqual(self.config.read_text(), 'web-portal 1000')
        self.assertEqual(calls.call_args_list[-1].args, ('exec', '-T', 'web-gateway', 'nginx', '-s', 'reload'))

    def test_linux_timer_is_short_lived_and_boot_starts_stack(self):
        units = install_linux.units(PurePosixPath('/srv/map app'), '/usr/bin/python3', 'deploy')
        self.assertIn('OnUnitInactiveSec=5min', units['map-predict-update.timer'])
        self.assertIn('Type=oneshot', units['map-predict-update.service'])
        self.assertIn('"/srv/map app/tools/auto_deploy.py"', units['map-predict-update.service'])
        self.assertIn('WorkingDirectory=/srv/map app\n', units['map-predict-update.service'])
        self.assertIn('Requires=docker.service', units['map-predict-stack.service'])
        self.assertIn('User=deploy', units['map-predict-stack.service'])
        self.assertIn('start --no-build', units['map-predict-stack.service'])

    def test_boot_can_reuse_prebuilt_images_without_a_build(self):
        with patch.object(docker_stack, 'compose', return_value='') as calls:
            docker_stack.start(no_build=True)
        self.assertEqual(calls.call_args_list[0].args,
                         ('up', '-d', '--no-build', '--wait', '--wait-timeout', '180'))

    def test_low_memory_policy_preserves_other_settings_and_comments(self):
        original = '# vm.swappiness = 0\nnet.ipv4.ip_forward = 1\nvm.swappiness = 0\nvm.swappiness=30\n'
        result = install_linux.memory_sysctl(original)
        self.assertIn('# vm.swappiness = 0\n', result)
        self.assertIn('net.ipv4.ip_forward = 1\n', result)
        self.assertEqual(result.count('\nvm.swappiness = 60\n'), 1)
        self.assertEqual(result.splitlines()[-2:], ['vm.swappiness = 60', 'vm.swappiness = 60'])
        self.assertEqual(install_linux.memory_sysctl(result), result)
        self.assertEqual(install_linux.memory_sysctl('net.ipv4.ip_forward=1\n'),
                         'net.ipv4.ip_forward=1\nvm.swappiness = 60\n')


if __name__ == '__main__':
    unittest.main()
