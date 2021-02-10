==============================================
appackager -- build .deb packages using pipenv
==============================================


Release history
---------------

#. Incorporate computed build tag, including distro version if
   applicable, in package version recorded in metadata.


0.4.1 (2021-01-18)
~~~~~~~~~~~~~~~~~~

#. Fix inclusion of distribution identification in built package.


0.4.0 (2021-01-18)
~~~~~~~~~~~~~~~~~~

#. Update support for ``payload`` configuration sections to support
   directory trees as well as individual files.
   https://kt-git.keepertech.com/DevTools/appackager/issues/6

#. Include distribution identification in architecture-specific builds.
   https://kt-git.keepertech.com/DevTools/appackager/issues/5


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
