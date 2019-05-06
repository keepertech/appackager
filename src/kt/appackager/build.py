"""\
(c) 2019.  Keeper Technology LLC.  All Rights Reserved.
Use is subject to license.  Reproduction and distribution is strictly
prohibited.

Subject to the following third party software licenses and terms and
conditions (including open source):  www.keepertech.com/thirdpartylicenses

Main entry point for building packages.

"""

import distutils.version
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import textwrap

import kt.appackager.cli


logger = logging.getLogger(__name__)


def main():
    parser = kt.appackager.cli.ArgumentParser()
    settings = parser.parse_args()
    config = settings.config

    package = config.name
    build = Build(config)
    version = build.next_version()

    arch_specific = config.arch_specific
    if arch_specific:
        arch = subprocess.check_output(
            ['dpkg-architecture', '-q', 'DEB_BUILD_ARCH']).strip()
    else:
        arch = 'all'

    pkgdirname = f'{package}_{version}-1_{arch}'

    with tempfile.TemporaryDirectory() as tmpdir:
        topdir = os.path.join(tmpdir, pkgdirname)
        os.mkdir(topdir)
        os.mkdir(os.path.join(topdir, 'DEBIAN'))

        installation = config.directory
        assert installation.startswith('/')

        print(f'Building {package} in {topdir}')
        print(f'Installation directory: {installation}')

        libpython = installation + '/lib/python'
        os.makedirs(topdir + libpython)
        os.mkdir(topdir + installation + '/bin')

        subprocess.check_output(
            ['pipenv', '--bare', 'install', '--python', config.python])
        venvdir = subprocess.check_output(['pipenv', '--venv']).strip()
        os.chdir(venvdir)

        os.chdir(topdir + libpython)
        rc, out, err = subprocess.run(
            [config.python, '-m', 'compileall', '-fqq', '-d', libpython, '.'])
        subprocess.check(['chmod', '-R', 'go-w', topdir + installation])

        # mkscripts

        # On success, remember what we built:
        build.commit_version()


class Build(object):

    need_autoversion = False

    def __init__(self, config):
        self.config = config

    def next_version(self):
        stdout = subprocess.check_output(
            ['git', 'log', '--pretty=format:%h %D'])
        stdout = str(stdout, 'utf-8')

        tag = '0.0.0'
        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            hash, sp, rest = line.partition(' ')
            if rest:
                refs = [r.strip() for r in rest.split(',')]
                tags = [distutils.version.StrictVersion(_extract_version(r))
                        for r in refs
                        if (r.startswith('tag:') and _extract_version(r))]
                if tags:
                    tag = max(tags)
                    break
            self.need_autoversion = True

        tag = str(tag)

        if self.need_autoversion:
            self.avinfo = {}
            if os.path.exists(self.config.autoversion_file):
                with open(self.config.autoversion_file) as f:
                    self.avinfo = json.load(f)
            prev_base = self.avinfo.get('base_version')
            if prev_base == str(tag):
                # Same base version; get count:
                counter = self.avinfo.get('counter', 0) + 1
            else:
                self.avinfo['base_version'] = str(tag)
                counter = 1
            self.avinfo['counter'] = counter
            tag += 'a' + str(counter)

        return tag

    def commit_version(self):
        if self.need_autoversion:
            with open(self.config.autoversion_file, 'w') as f:
                json.dump(self.avinfo, f, indent=2, sort_keys=True)
                f.write('\n')

    def make_script(self, script):
        pass


def error(message):
    for line in textwrap.wrap(message, fix_sentence_endings=True):
        print(line, file=sys.stderr)
    sys.exit(1)


_version_re = r'tag: v?(\d+([.]\d+)+)$'
_version_rx = re.compile(_version_re)


def _extract_version(text):
    m = _version_rx.match(text)
    if m is None:
        return None
    return m.group(1)
