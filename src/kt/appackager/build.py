"""\
(c) 2019 - 2020.  Keeper Technology LLC.  All Rights Reserved.
Use is subject to license.  Reproduction and distribution is strictly
prohibited.

Subject to the following third party software licenses and terms and
conditions (including open source):  www.keepertech.com/thirdpartylicenses

Main entry point for building packages.

"""

import configparser
import contextlib
import distutils.version
import email
import glob
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap

import kt.appackager.cli


SCRIPT_TEMPLATE = '''\
#!{executable} -Es

import os
import sys

bin_dir = os.path.dirname(os.path.abspath(__file__))
top_dir = os.path.dirname(bin_dir)
lib_dir = os.path.join(top_dir, "lib")

for unwanted in ('', bin_dir):
    while unwanted in sys.path:
        sys.path.remove(unwanted)

# Toss base entries that do not exist or that contain distro add-ons:
sys.path[:] = [p for p in sys.path
               if os.path.exists(p) and not p.endswith('/dist-packages')]

# Add in the directory containing our application packages:
sys.path.insert(0, os.path.join(lib_dir, {pythondir!r}))

version = {version!r}

import {module}

{initialization}
if __name__ == "__main__":
    sys.exit({module}.{object}())
'''

logger = logging.getLogger(__name__)


def main():
    parser = kt.appackager.cli.ArgumentParser()
    settings = parser.parse_args()
    Build(settings.config).run()


class Build(object):

    need_autoversion = False

    # We excise these since they're part of the base Python installation
    # now.
    packages_to_excise = (
        'pip',
        'setuptools',
    )

    def __init__(self, config):
        self.config = config
        self.console_scripts = {}
        self._local_package = None

        self._mask = os.umask(2)
        os.umask(self._mask)

    def run(self):
        workdir = os.getcwd()
        version = self.version = self.next_version()

        arch_specific = self.config.arch_specific
        if arch_specific:
            arch = subprocess.check_output(
                ['dpkg-architecture', '-q', 'DEB_BUILD_ARCH'])
            arch = str(arch, 'utf-8').strip()
        else:
            arch = 'all'

        deb_version = version
        if 'a' in version:
            deb_version = version.replace('a', '~a')

        pkgdirname = f'{self.config.name}_{deb_version}-1_{arch}'
        debname = pkgdirname + '.deb'

        with tempfile.TemporaryDirectory() as tmpdir:
            topdir = os.path.join(tmpdir, pkgdirname)
            debdir = os.path.join(topdir, 'DEBIAN')
            os.mkdir(topdir)
            os.mkdir(debdir)

            installation = self.config.directory
            assert installation.startswith('/')

            print(f'Building {self.config.name} in {topdir}')
            print(f'Installation directory: {installation}')

            with SavedPipenvVenv():
                with self.non_editable_pipfile_lock():
                    subprocess.check_output(
                        ['pipenv', '--bare', 'install',
                         '--python', self.config.python])

                    # Determine where site-packages is, because we need that
                    # to locate the *.dist-info directories, so we can make
                    # use of the entry point metadata.
                    #
                    pip_init = subprocess.check_output(
                        ['pipenv', 'run', 'python', '-c',
                         'import os, pip\n'
                         'print(os.path.abspath(pip.__file__))'])
                    pip_init = str(pip_init, 'utf-8').strip()

                # We no longer need to build using pipenv; that should
                # only happen inside the context above.

                self.site_packages = os.path.dirname(os.path.dirname(pip_init))
                assert self.site_packages.endswith('/site-packages')
                pythondir = os.path.basename(
                    os.path.dirname(self.site_packages))
                self.pythondir = pythondir

                self.excise_packages()

                libpython = installation + '/lib/' + pythondir
                os.makedirs(topdir + libpython)

                # ---

                os.chdir(self.site_packages)
                pack = subprocess.Popen(
                    ['tar', 'c', '.'], stdout=subprocess.PIPE)
                unpack = subprocess.Popen(
                    ['tar', 'x', '-C', topdir + libpython], stdin=pack.stdout)
                pack.stdout.close()
                out, err = unpack.communicate()

                # ---

                os.chdir(topdir + libpython)
                subprocess.run(
                    [self.config.python, '-m', 'compileall', '-fqq',
                     '-d', libpython, '.'])
                subprocess.check_call(
                    ['chmod', '-R', 'go-w', topdir + installation])
                os.chdir(workdir)

                # Generate scripts while we still have the build venv;
                # we need it to collect the entry point data from the
                # *.dist-info directories.
                #
                if self.config.scripts:
                    bindir = topdir + installation + '/bin'
                    os.mkdir(bindir)
                    for script in self.config.scripts:
                        self.make_script(script, bindir)
                    subprocess.check_call(['chmod', '-R', 'a-w', bindir])

            for shscript in glob.glob('debian/*'):
                # TODO: Limit the allowed names of the script files to those
                # that make sense as Debian installation hooks.
                basename = os.path.basename(shscript)
                shutil.copy(shscript, os.path.join(debdir, basename))

            with open(debdir + '/control', 'w') as f:
                print(f'Package: {self.config.name}', file=f)
                print(f'Version: {deb_version}-1', file=f)
                if self.config.description:
                    print(f'Description: {self.config.description}', file=f)
                if self.config.maintainer:
                    print(f'Maintainer: {self.config.maintainer}', file=f)
                    print(f'Architecture: {arch}', file=f)
                    print(f'Priority: {self.config.priority}', file=f)

                def dependencies(attr, label):
                    deps = getattr(self.config, attr, ())
                    if deps:
                        deps = ', '.join(deps)
                        print(f'{label}: {deps}', file=f)

                dependencies('requires', 'Depends')
                dependencies('conflicts', 'Conflicts')
                dependencies('provides', 'Provides')

            for payload in self.config.payloads:
                destination = payload['destination']
                if '/' in destination:
                    dest_dir, dest_name = destination.rsplit('/', 1)
                    dest_dir = topdir + os.path.join(installation, dest_dir)
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)
                else:
                    dest_dir = topdir + installation
                    dest_name = destination
                destination = os.path.join(dest_dir, dest_name)
                source = os.path.join(workdir, payload['source'])
                shutil.copy(source, destination)

            # Build the actual .deb:

            os.chdir(tmpdir)
            subprocess.check_call(
                ['fakeroot', 'dpkg-deb', '-z9', '-Zgzip', '-b', pkgdirname])
            os.chdir(workdir)
            if not os.path.exists('packages'):
                os.mkdir('packages')
            subprocess.check_call(
                ['mv', os.path.join(tmpdir, debname), 'packages/'])

            # On success, remember what we built:
            self.commit_version()

            subprocess.check_call(
                ['chmod', 'a-w', os.path.join('packages', debname)])
            subprocess.check_call(['chmod', '-R', 'u+w', tmpdir])

    def excise_packages(self):
        outside_prefix = os.pardir + os.sep
        # The set of dirs in site-packages we touched.
        dirs = set()
        for pkgname in self.packages_to_excise:
            distinfo = self.get_package_distinfo(pkgname)
            record = os.path.join(distinfo, 'RECORD')
            for line in open(record):
                path, chksum, size = line.rsplit(',', 2)
                if path.startswith(outside_prefix):
                    # Not under site-packages; stay away.
                    continue
                dirs.add(path.split(os.sep, 1)[0])
                path = os.path.normpath(os.path.join(self.site_packages, path))
                if os.path.exists(path):
                    os.unlink(path)
        for dirname in dirs:
            path = os.path.normpath(os.path.join(self.site_packages, dirname))
            for dirpath, dirnames, filenames in os.walk(path, topdown=False):
                # Need to re-compute dirnames, since we may have removed
                # the directories that are included.
                dirnames = {dname for dname in dirnames
                            if os.path.isdir(os.path.join(dirpath, dname))}
                if filenames or dirnames:
                    print(f'directory {dirpath} not empty')
                else:
                    os.rmdir(dirpath)

    @contextlib.contextmanager
    def non_editable_pipfile_lock(self):
        has_editable = False
        lockname = 'Pipfile.lock'
        tmpname = lockname + '.orig'

        if os.path.isfile(lockname):
            with open(lockname) as orig:
                content = json.load(orig)
                for k, v in content.items():
                    if k in ('default', 'develop'):
                        for pkgname, info in v.items():
                            if info.get('editable'):
                                has_editable = True
                                info['editable'] = False

        if has_editable:
            os.rename(lockname, tmpname)
            with open(lockname, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=4, sort_keys=True)

        yield

        if has_editable:
            os.rename(lockname, lockname + '.used')
            os.rename(tmpname, lockname)

    def next_version(self):
        stdout = subprocess.check_output(
            ['git', 'log', '--pretty=format:%h %D'])
        stdout = str(stdout, 'utf-8')

        tag = distutils.version.StrictVersion('0.0.0')
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

        # We don't use str(tag) because StrictVersion.__str__ drops the
        # third element if it's 0.  That's ambiguous, and we don't want
        # that.

        major, minor, patch = tag.version
        suffix = ''
        if self.need_autoversion:
            tag = '%d.%d.%d' % (major, minor, patch + 1)
            self.avinfo = {}
            if os.path.exists(self.config.autoversion_file):
                with open(self.config.autoversion_file) as f:
                    self.avinfo = json.load(f)
            prev_base = self.avinfo.get('base_version')
            if prev_base == str(tag):
                # Same base version; get count:
                counter = self.avinfo.get('counter', 0) + 1
            else:
                self.avinfo['base_version'] = tag
                counter = 1
            self.avinfo['counter'] = counter
            suffix = 'a' + str(counter)

        return '%d.%d.%d%s' % (major, minor, patch, suffix)

    def commit_version(self):
        if self.need_autoversion:
            with open(self.config.autoversion_file, 'w') as f:
                json.dump(self.avinfo, f, indent=2, sort_keys=True)
                f.write('\n')

    def make_script(self, script, directory):
        executable = self.config.python
        entrypoint = script.entrypoint
        if ':' in entrypoint:
            dist, name = entrypoint.split(':', 1)
        else:
            dist = ''
            name = entrypoint
        if not dist:
            dist = self.get_local_dist(script)
        if dist not in self.console_scripts:
            self.get_console_scripts(dist)
        console_scripts = self.console_scripts[dist]
        if name not in console_scripts:
            print(f'[script.{script.name}] specifies non-existent'
                  f' entry-point {name!r}', file=sys.stderr)
            sys.exit(1)
        module, object = console_scripts[name].split(':')
        script_body = SCRIPT_TEMPLATE.format(
            executable=executable,
            initialization=script.initialization,
            module=module,
            object=object,
            pythondir=self.pythondir,
            version=self.version,
        )
        target = os.path.join(directory, script.name)
        with open(target, 'w') as f:
            f.write(script_body)
        os.chmod(target, 0o777 - self._mask)

    def get_local_dist(self, script):
        if self._local_package:
            return self._local_package

        if self._local_package is None:
            if os.path.exists('setup.py'):
                appackagerdir = os.path.dirname(os.path.abspath(__file__))
                site_packages = os.path.dirname(os.path.dirname(appackagerdir))
                with tempfile.TemporaryDirectory() as tmpdir:
                    subprocess.check_call(
                        [self.config.python, 'setup.py', '-q',
                         'dist_info', '--egg-base', tmpdir],
                        env={'PYTHONPATH': site_packages})
                    dist_info = os.path.join(tmpdir, os.listdir(tmpdir)[0])
                    with open(os.path.join(dist_info, 'METADATA')) as f:
                        msg = email.message_from_file(f)
                        self._local_package = msg['name']

        if not self._local_package:
            print(f'[script.{script.name}] entrypoint refers to the'
                  f' local package, but there is no setup.py',
                  file=sys.stderr)
            sys.exit(1)
        return self._local_package

    def get_console_scripts(self, pkgname):
        distinfo = self.get_package_distinfo(pkgname)
        console_scripts = {}
        entry_point_path = os.path.join(distinfo, 'entry_points.txt')
        try:
            with open(entry_point_path) as f:
                cfg = configparser.RawConfigParser()
                cfg.read_file(f, entry_point_path)
                for name in cfg.options('console_scripts'):
                    console_scripts[name] = cfg.get('console_scripts', name)
        except Exception:
            pass
        self.console_scripts[pkgname] = console_scripts

    def get_package_distinfo(self, pkgname):
        pattern = os.path.join(self.site_packages, f'{pkgname}-*.dist-info')
        dirs = glob.glob(pattern)
        assert len(dirs) == 1, dirs
        return dirs[0]


class SavedPipenvVenv(object):

    def __init__(self):
        super(SavedPipenvVenv, self).__init__()
        self.moved_aside = None
        self.original = self.locate()

    def locate(self):
        venv = None
        cp = subprocess.run(['pipenv', '--venv'],
                            capture_output=True, encoding='utf-8')
        if not cp.returncode:
            venv = cp.stdout
            if venv.endswith('\n'):
                venv = venv[:-1]
        return venv

    def __enter__(self):
        if self.original:
            self.moved_aside = self.original + '-saved'
            if os.path.isdir(self.moved_aside):
                # This really isn't good; what to do?
                print("There's already a saved virtual environment,"
                      " and another to save.", file=sys.stderr)
                sys.exit(1)
            os.rename(self.original, self.moved_aside)
        return self

    def __exit__(self, typ, value, tb):
        venv = self.original or self.locate()
        bad_build = venv + '-failed'

        if os.path.isdir(bad_build):
            print('Discarding outdated failed build.')
            shutil.rmtree(bad_build)

        if typ is None:
            # Success.  Discard venv.
            if venv:
                shutil.rmtree(venv)
        else:
            # Failure.  Save failed build.
            if venv:
                print('Saving virtual environment from failed'
                      ' build as:', bad_build)
                os.rename(venv, bad_build)
        if self.original:
            os.rename(self.moved_aside, self.original)


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
