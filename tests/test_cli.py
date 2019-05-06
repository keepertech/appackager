"""\
(c) 2019.  Keeper Technology LLC.  All Rights Reserved.
Use is subject to license.  Reproduction and distribution is strictly
prohibited.

Subject to the following third party software licenses and terms and
conditions (including open source):  www.keepertech.com/thirdpartylicenses

Tests for kt.appackager.cli.

"""

import os.path
import sys
import unittest

import kt.appackager.cli


here = os.path.dirname(os.path.abspath(__file__))
sample_toml = os.path.join(here, 'sample.toml')


class CLITestCase(unittest.TestCase):

    def setUp(self):
        argv = list(sys.argv)

        def restore_argv():
            sys.argv[:] = argv

        self.addCleanup(restore_argv)

    def test_basic_config(self):
        sys.argv[1:] = ['-c', sample_toml]
        parser = kt.appackager.cli.ArgumentParser()
        psettings = parser.parse_args()
        config = psettings.config

        self.assertEqual(len(config.scripts), 3)
        by_name = {script.name: script
                   for script in config.scripts}
        self.assertIn('kt.tracing.bootstrap()',
                      by_name['ki-spaces'].initialization)
        self.assertIn('kt.tracing.bootstrap()',
                      by_name['script-next'].initialization)
        self.assertIn('kt.tracing.disable()',
                      by_name['script-name'].initialization)
