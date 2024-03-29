"""\
Command-line & configuration-loading support.

"""

import argparse
import logging

import tomli


DEFAULT_AUTOVERSION_FILE = '.autoversion.json'
DEFAULT_HOOK_SCRIPTS = 'debian'

logger = logging.getLogger(__name__)


class ArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super(ArgumentParser, self).__init__(*args, **kwargs)
        self.set_defaults(verbose=0)
        self.add_argument('-c', '--configuration', default='appackager.toml')
        self.add_argument('--set-version', action='store')
        vg = self.add_mutually_exclusive_group()
        vg.add_argument('-v', '--verbose', action='count')
        vg.add_argument('--verbosity', action='store',
                        dest='verbose', type=int)

    def parse_args(self):
        namespace = super(ArgumentParser, self).parse_args()
        with open(namespace.configuration, 'rb') as cf:
            namespace.config = Configuration(tomli.load(cf))
        namespace.config.set_version = namespace.set_version
        return namespace


_marker = object()

_toml_types = {
    'array': list,
    'boolean': bool,
    'float': float,
    'integer': int,
    'string': str,
    'table': dict,
}


class Configuration(object):

    def __init__(self, config):
        self._config = config
        # Make sure everything is computed and checked.
        self.name = self._get('package', 'name')
        self.description = self._config['package'].get('description')
        self.maintainer = self._config['package'].get('maintainer')
        self.priority = self._config['package'].get('priority', 'optional')
        self.scripts = self._scripts()
        self.directory = self._get('installation', 'directory')
        self.packages_to_excise = self._get('installation', 'excise-packages',
                                            type='array',
                                            default=[])
        self.python = self._get('installation', 'python')

        self.hook_scripts = self._get('package', 'hook-scripts',
                                      default=DEFAULT_HOOK_SCRIPTS)

        # Need to have a separate 'not-specified' / 'auto-detect' value;
        # need not be something user can spell out explicitly.
        #
        # Must *not* default to False.
        #
        try:
            self.arch_specific = self._get('package', 'architecture-specific',
                                           type='boolean')
        except KeyError:
            self.arch_specific = None

        self.autoversion_file = self._get('autoversion-file',
                                          default=DEFAULT_AUTOVERSION_FILE)

        self.requires = self._dependencies('requires')
        self.conflicts = self._dependencies('conflicts')
        self.provides = self._dependencies('provides')

        try:
            self.payloads = [
                dict(payload, name=name)
                for name, payload in self._get('payload', type='table').items()
            ]
        except KeyError:
            self.payloads = []

    def _get(self, *names, type='string', default=_marker):
        table_names, name = self._split_names(names)
        path = ''
        cfg = self._config
        for nm in table_names:
            if path:
                path += '.'
            path += nm
            try:
                cfg = cfg[nm]
            except KeyError:
                if default is not _marker:
                    return default
                raise
            if not isinstance(cfg, dict):
                raise TypeError(f'[{path}] must be a table')
        value = cfg.get(name, default)
        if value is _marker:
            raise KeyError(f'[{path}] {name} is not configured')
        vtype = _toml_types[type]
        if not isinstance(value, vtype):
            raise TypeError(f'[{path}] {name} must be a {type};'
                            f' found {value.__class__.__name__}')
        return value

    def _dependencies(self, *names):
        table_names, name = self._split_names(('dependencies',) + names)
        if table_names:
            cfg = self._get(*table_names, type='table')
        else:
            cfg = self._config
        if name in cfg:
            value = cfg[name]
        else:
            return []
        for val in value:
            if not isinstance(val, str):
                prefix = ''
                if table_names:
                    prefix = '[%s] ' % '.'.join(table_names)
                raise ValueError(f'[{prefix}] {name}')
        return value

    def _split_names(self, names):
        if not names:
            raise TypeError('at least one component name must be provided')
        return names[:-1], names[-1]

    def _scripts(self):
        initialization = self._get('scripts', 'initialization', default='')
        if initialization.rstrip():
            initialization = initialization.rstrip() + '\n'
        else:
            initialization = ''
        section = self._config.get('script', {})
        if not isinstance(section, dict):
            raise TypeError('[script] must be a table')

        scripts = []
        for name, subsection in section.items():
            if not isinstance(subsection, dict):
                raise TypeError(f'[script.{name}] must be a table')
            # Really expect this to be a script definition.
            if 'initialization' not in subsection:
                subsection['initialization'] = initialization
            scripts.append(self._script_definition(name, subsection))

        return tuple(scripts)

    def _script_definition(self, name, section):
        entrypoint = self._get('script', name, 'entry-point')
        initialization = self._get('script', name, 'initialization')
        return Script(
            name,
            entrypoint=entrypoint,
            initialization=initialization,
        )


class Script(object):

    def __init__(self, name,
                 entrypoint=None, main=None, initialization=None):
        self.name = name
        self.entrypoint = entrypoint
        self.initialization = initialization
