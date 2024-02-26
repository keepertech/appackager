==============================================
appackager -- build .deb packages using pipenv
==============================================


Release history
---------------


0.9.0 (2024-02-26)
~~~~~~~~~~~~~~~~~~

#. Add Python 3.12 to default test plan.  Removed Python prior to 3.10.
#. Added **--set-version** option to set the version of the generated Debian
   package file when building a package where the git repository is not
   available.
   https://github.com/keepertech/appackager/issues/4


0.8.0 (2024-02-25)
~~~~~~~~~~~~~~~~~~

#. Allow use of a symlink to provide more convenient access to installed
   scripts without failing to locate the installed Python packages.
   https://github.com/keepertech/appackager/issues/3


0.7.0 (2023-06-14)
~~~~~~~~~~~~~~~~~~

#. Store last alpha for each base version, to better support switching
   branches in working copy.
#. Switch to ``tomli`` for TOML parsing; older ``toml`` library appears
   to have disappeared.
#. Remove "kt-" from package name.
#. Update supported Python versions.
#. Avoid deprecation warnings from updated packaging libraries.
#. Excise nothing by default.


0.6.2 (2022-09-23)
~~~~~~~~~~~~~~~~~~

#. Fix reliability issue in locating dist-info directory for an
   installed package.

#. When excising a package that should not be installed, remove the
   left-over empty dist-info directory from that package.


0.6.1 (2022-08-23)
~~~~~~~~~~~~~~~~~~

#. Fix missing import of TOML parser for reading pyproject.toml files.


0.6.0 (2021-07-06)
~~~~~~~~~~~~~~~~~~

#. Run script initialization before importing the module providing the
   configured console script entry point.  This allows things like
   warning configurations to be arranged before too many imports have
   been executed.

#. Support configuration of the packages that should be excised from the
   installation before the platform package is built.


0.5.0 (2021-04-02)
~~~~~~~~~~~~~~~~~~

#. If there's no setup.py in the package being built, and we actually
   need to identify the local package, also check in setup.cfg or
   pyproject.toml.  Report which source provided the name.

#. Recognize need to auto-version a pre-release when there are local
   changes directly over a tagged release.


0.4.2 (2021-02-10)
~~~~~~~~~~~~~~~~~~

#. Incorporate computed build tag, including distro version if
   applicable, in package version recorded in metadata.


0.4.1 (2021-01-18)
~~~~~~~~~~~~~~~~~~

#. Fix inclusion of distribution identification in built package.


0.4.0 (2021-01-18)
~~~~~~~~~~~~~~~~~~

#. Update support for ``payload`` configuration sections to support
   directory trees as well as individual files.

#. Include distribution identification in architecture-specific builds.


0.3.0 (2020-01-10)
~~~~~~~~~~~~~~~~~~

#. Auto-detect architecture-specific builds, instead of requiring a
   configuration flag to indicate.


0.2.0 (2020-01-06)
~~~~~~~~~~~~~~~~~~

#. Default to architecture-specific builds.


0.1.0 (2020-01-03)
~~~~~~~~~~~~~~~~~~

Initial release, internal to Keeper Technology.
