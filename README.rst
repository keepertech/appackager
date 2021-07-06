==============================================
appackager -- build .deb packages using pipenv
==============================================


Release history
---------------


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
   https://kt-git.keepertech.com/DevTools/appackager/-/issues/7


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
   https://kt-git.keepertech.com/DevTools/appackager/-/issues/6

#. Include distribution identification in architecture-specific builds.
   https://kt-git.keepertech.com/DevTools/appackager/-/issues/5


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
