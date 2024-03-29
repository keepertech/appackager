"""\
Main entry point for building packages.

"""

import configparser
import contextlib
import distutils.version
import email
import fnmatch
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

import tomli

import kt.appackager.cli


SCRIPT_TEMPLATE = '''\
#!{executable} -Es

import os
import sys


def unlinkify(path):
    if os.path.islink(path):
        return os.path.realpath(path)
    else:
        return os.path.abspath(path)

bin_dir = os.path.dirname(unlinkify(__file__))
top_dir = os.path.dirname(unlinkify(bin_dir))
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

{initialization}
import {module}

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

    def __init__(self, config):
        self.config = config
        self.console_scripts = {}
        self._local_package = None

        self._mask = os.umask(2)
        os.umask(self._mask)

    def run(self):
        workdir = os.getcwd()
        version = self.version = self.next_version()

        deb_version = version
        if 'a' in version:
            deb_version = version.replace('a', '~a')

        with tempfile.TemporaryDirectory() as tmpdir:
            installation = self.config.directory
            assert installation.startswith('/')

            print(f'Building package: {self.config.name}')
            print(f'Installation directory: {installation}')

            with SavedPipenvVenv():
                with self.non_editable_pipfile_lock():
                    subprocess.check_output(
                        ['pipenv', '--bare', 'sync',
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
                self.pythondir = os.path.basename(
                    os.path.dirname(self.site_packages))

                # Clean out the things we do not need:
                self.excise_packages()

                # ---

                os.chdir(self.site_packages)

                # Need to determine whether any installed packages are
                # platform-specific.  We can look at the *.dist-info
                # directories to determine this.
                #
                # This affects the arch_specific flag and computed
                # pkgdirname, topdir, debdir values.

                arch_specific = self.config.arch_specific
                if self.included_arch_specific_packages():
                    if arch_specific is None:
                        arch_specific = True
                    elif arch_specific is False:
                        # Configuration says false, but we have
                        # arch-specific packages in the build.
                        print('Including architecture specific components in'
                              ' build, but configuration says the package is'
                              ' architecture independent.')
                else:
                    arch_specific = False
                assert isinstance(arch_specific, bool)

                build = '1'
                if arch_specific:
                    arch = subprocess.check_output(
                        ['dpkg-architecture', '-q', 'DEB_BUILD_ARCH'])
                    arch = str(arch, 'utf-8').strip()

                    distro_name = subprocess.check_output(
                        ['lsb_release', '--id', '--short'])
                    distro_name = str(distro_name, 'utf-8').strip()

                    distro_version = subprocess.check_output(
                        ['lsb_release', '--release', '--short'])
                    distro_version = str(distro_version, 'utf-8').strip()

                    build += distro_name.lower() + distro_version
                else:
                    arch = 'all'

                pkgdirname = f'{self.config.name}_{deb_version}-{build}_{arch}'
                debname = pkgdirname + '.deb'

                topdir = os.path.join(tmpdir, pkgdirname)
                debdir = os.path.join(topdir, 'DEBIAN')
                libpython = installation + '/lib/' + self.pythondir

                os.mkdir(topdir)
                os.mkdir(debdir)
                os.makedirs(topdir + libpython)

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
                print(f'Version: {deb_version}-{build}', file=f)
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
                if os.path.isdir(source):
                    shutil.copytree(source, destination)
                else:
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
        print('preparing to excise:', self.config.packages_to_excise)
        for pkgname in self.config.packages_to_excise:
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
            # Avoid leaving an empty dist-info directory, even temporarily.
            os.rmdir(distinfo)
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

    def included_arch_specific_packages(self):
        for wheelfn in glob.glob('*.dist-info/WHEEL'):
            with open(wheelfn) as f:
                text = f.read()
            message = email.message_from_string(text)
            for tag in message.get_all('tag'):
                pytag, abitag, platformtag = tag.split('-')
                if platformtag != 'any':
                    return True
        return False

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
        if os.path.exists('.git'):
            if self.config.set_version:
                print('cannot use --set-version when used in conjunction'
                      ' with a git repository', file=sys.stderr)
                sys.exit(1)
            return self.next_version_from_git()
        elif self.config.set_version:
            return self.config.set_version
        else:
            print('use --set-version when running without access to a'
                  ' git repository', file=sys.stderr)
            sys.exit(1)

    def next_version_from_git(self):
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

        if not self.need_autoversion:
            # Check for local changes in the working copy:
            stdout = subprocess.check_output(
                ['git', 'status', '--porcelain', '.'])
            self.need_autoversion = bool(stdout.strip())

        # We don't use str(tag) because StrictVersion.__str__ drops the
        # third element if it's 0.  That's ambiguous, and we don't want
        # that.

        major, minor, patch = tag.version
        suffix = ''
        if self.need_autoversion:
            patch += 1
            base = f'{major}.{minor}.{patch}'
            self.avinfo = {}
            if os.path.exists(self.config.autoversion_file):
                with open(self.config.autoversion_file) as f:
                    self.avinfo = json.load(f)
            if base not in self.avinfo:
                if 'base_version' in self.avinfo:
                    prev_base = self.avinfo['base_version']
                    self.avinfo[prev_base] = self.avinfo.pop('counter', 0)
                    del self.avinfo['base_version']
            counter = self.avinfo.get(base, 0) + 1
            self.avinfo[base] = counter
            suffix = f'a{counter}'

        return f'{major}.{minor}.{patch}{suffix}'

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

        found = None
        if self._local_package is None:
            if os.path.exists('setup.py'):
                appackagerdir = os.path.dirname(os.path.abspath(__file__))
                site_packages = os.path.dirname(os.path.dirname(appackagerdir))
                with tempfile.TemporaryDirectory() as tmpdir:
                    subprocess.check_call(
                        # sys.executable here is from the running appackager
                        # build, so includes the required wheel support:
                        [sys.executable, 'setup.py', '-q',
                         'dist_info', '--output-dir', tmpdir],
                        env={'PYTHONPATH': site_packages})
                    dist_info = os.path.join(tmpdir, os.listdir(tmpdir)[0])
                    with open(os.path.join(dist_info, 'METADATA')) as f:
                        msg = email.message_from_file(f)
                        self._local_package = msg['name']
                        found = 'using setup.py'

            elif os.path.exists('setup.cfg'):
                conf = configparser.ConfigParser(interpolation=None)
                with open('setup.cfg') as f:
                    conf.read_file(f, 'setup.cfg')
                try:
                    self._local_package = conf.get('metadata', 'name')
                except configparser.Error:
                    print(f'[script.{script.name}] entrypoint refers to the'
                          f' local package, but the package name is not'
                          f' present in setup.cfg',
                          file=sys.stderr)
                    sys.exit(1)
                else:
                    found = 'in setup.cfg'

            elif os.path.exists('pyproject.toml'):
                with open('pyproject.toml', 'rb') as ppf:
                    conf = tomli.load(ppf)
                project = conf.get('project')
                if isinstance(project, dict):
                    name = project.get('name')
                    if isinstance(name, str):
                        self._local_package = name
                        found = 'in pyproject.toml'

                if not self._local_package:
                    print(f'[script.{script.name}] entrypoint refers to the'
                          f' local package, but the package name could not'
                          f' be located in pyproject.toml',
                          file=sys.stderr)
                    sys.exit(1)

        if not self._local_package:
            print(f'[script.{script.name}] entrypoint refers to the local'
                  f' package, but package metadata could not be located',
                  file=sys.stderr)
            sys.exit(1)
        print(f'extracted local package name {self._local_package!r} {found}')
        return self._local_package

    def get_console_scripts(self, pkgname):
        distinfo = self.get_package_distinfo(pkgname)
        console_scripts = {}
        entry_point_path = os.path.join(distinfo, 'entry_points.txt')
        try:
            with open(entry_point_path) as f:
                cfg = configparser.ConfigParser(interpolation=None)
                cfg.read_file(f, entry_point_path)
                for name in cfg.options('console_scripts'):
                    console_scripts[name] = cfg.get('console_scripts', name)
        except Exception:
            pass
        self.console_scripts[pkgname] = console_scripts

    def get_package_distinfo(self, pkgname):
        #
        # Looping over all the dist-info directories doesn't seem very
        # efficient, but is reliable in the face of concerns regarding
        # package name normalization described in:
        #
        # https://discuss.python.org/t/
        # revisiting-distribution-name-normalization/
        #
        for fn in fnmatch.filter(os.listdir(self.site_packages),
                                 '*.dist-info'):
            mdpath = os.path.join(self.site_packages, fn, 'METADATA')

            # While excising packages that are not wanted, an empty
            # dist-info directory can get left behind temporarily; we
            # want to be resilient in that case.
            #
            # This should no longer happen with changes in the excise
            # code, but has been observed during the evolution of this.
            #
            if not os.path.exists(mdpath):
                continue

            with open(mdpath) as f:
                msg = email.message_from_file(f)
                if msg['name'] == pkgname:
                    return os.path.join(self.site_packages, fn)
        return None


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
