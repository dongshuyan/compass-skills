import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class HookReadinessTests(unittest.TestCase):
    def check(self, hooks):
        from title_plugin import hook_readiness
        return hook_readiness({'data': [{'cwd': '/test', 'hooks': hooks, 'errors': []}]},
                              'titles@project', Path('/test'))

    def hook(self, event, trust='trusted', enabled=True, plugin='titles@project'):
        return {'pluginId': plugin, 'eventName': event, 'trustStatus': trust, 'enabled': enabled}

    def test_untrusted_hooks_are_not_reported_as_ready(self):
        value = self.check([self.hook('userPromptSubmit', 'untrusted'), self.hook('stop', 'untrusted')])
        self.assertFalse(value['runtime_ready'])
        self.assertTrue(value['needs_hook_review'])

    def test_both_enabled_trusted_hooks_are_required(self):
        self.assertTrue(self.check([self.hook('userPromptSubmit'), self.hook('stop')])['runtime_ready'])
        self.assertFalse(self.check([self.hook('userPromptSubmit')])['runtime_ready'])
        self.assertFalse(self.check([self.hook('userPromptSubmit'), self.hook('stop', enabled=False)])['runtime_ready'])

    def test_changed_hook_requires_review_again(self):
        value = self.check([self.hook('userPromptSubmit'), self.hook('stop', 'modified')])
        self.assertFalse(value['runtime_ready'])
        self.assertTrue(value['needs_hook_review'])

    def test_another_plugins_hooks_cannot_satisfy_readiness(self):
        self.assertFalse(self.check([self.hook('userPromptSubmit', plugin='other'),
                                     self.hook('stop', plugin='other')])['runtime_ready'])


if __name__ == '__main__':
    unittest.main()
