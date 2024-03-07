==============================================
appackager -- build .deb packages using pipenv
==============================================


Bootstrapping appackager
------------------------

Since a primary goal of |appackager| is to build application packages that use
a non-system Python, start by ensuring such an installation is available and
can be referenced as a system package.  |appackager| has been tested with the
packages built using the script from the `python-deb-packages`_ repository.
These packages provide fairly full-featured CPython installations in
directories named for the major/minor version of Python in
**/opt/cleanpythonXY**.  Executables from the Python installation do not need
to be available via the PATH.

|appackager| relies on |pipenv|_ to work, and is itself built using |pipenv|_.
Due to a bug (`issue 6054`_), |pipenv|_ versions newer than **2023.7.23**
cannot be used.  The |pipenv|_ command-line tool needs to be available via the
PATH.

If |pipx|_ is used to manage Python tool installations, install |pipenv|_
using that:

.. code-block:: shell-session

  $ pipx install --python /opt/cleanpythonXY/bin/python3 pipenv==2023.7.23

If |pipx|_ is not used, create a separate virtual environment for |pipenv|_
and install it there:

.. code-block:: shell-session

  $ mkdir -p ~/tools
  $ cd ~/tools
  $ /opt/cleanpythonXY/bin/python3 -m venv pipenv
  $ cd pipenv
  $ bin/pip install pipenv==2023.7.23

The installed |pipenv|_ can then be linked from a personal directory appearing
on PATH:

.. code-block:: shell-session

  $ cd ~/.local/bin
  $ ln -s ~/tools/pipenv/bin/pipenv* .

To build an installable |appackager| package, we'll need to build a
non-installed version using |pipenv|_, and then use that from a separate
worktree to build a Debian package.  This is a little more involved than for
applications, but is required since we want to run a copy of the built
software that won't be moved out of the way while it's running.

Switch to the directory with the **git** clone of the repository and run
**pipenv sync**:

.. code-block:: shell-session

  $ cd ~/projects/appackager
  $ pipenv sync
  Creating a virtualenv for this project...
  Pipfile: /home/myuser/projects/appackager/Pipfile
  Using default python from /home/myuser/.local/pipx/venvs/pipenv/bin/python (3.11.8) to create virtualenv...
  ⠋ Creating virtual environment...created virtual environment CPython3.11.8.final.0-64 in 83ms
    creator CPython3Posix(dest=/home/myuser/.local/share/virtualenvs/appackager-gWJbBuvh, clear=False, no_vcs_ignore=False, global=False)
    seeder FromAppData(download=False, pip=bundle, setuptools=bundle, wheel=bundle, via=copy, app_data_dir=/home/myuser/.local/share/virtualenv)
      added seed packages: pip==24.0, setuptools==69.1.0, wheel==0.42.0
    activators BashActivator,CShellActivator,FishActivator,NushellActivator,PowerShellActivator,PythonActivator

  ✔ Successfully created virtual environment!
  Virtualenv location: /home/myuser/.local/share/virtualenvs/appackager-gWJbBuvh
  Installing dependencies from Pipfile.lock (4a8ba2)...
  To activate this project's virtualenv, run pipenv shell.
  Alternatively, run a command inside the virtualenv with pipenv run.
  All dependencies are now up-to-date!

We need to create a second worktree for our clone; this doesn't need to be a
separate clone, but a second worktree for the same clone can be used.  This
command will create that worktree from the same commit we have in the primary
worktree of our clone:

.. code-block:: shell-session

  $ git worktree add ../appackager-alt $(git log -1 --format=%H)

From the new worktree, we can use the |appackager| we just built to create a
Debian package representing the commit we just checked out:

.. code-block:: shell-session

  $ appackage=$(pipenv --venv)/bin/appackage
  $ cd ../appackage-alt
  $ $appackage
  Building package: appackager
  Installation directory: /opt/appackager
  Creating a virtualenv for this project...
  Pipfile: /home/myuser/projects/appackager-alt/Pipfile
  Using /opt/cleanpython311/bin/python3 (3.11.8) to create virtualenv...
  created virtual environment CPython3.11.8.final.0-64 in 68ms
    creator CPython3Posix(dest=/home/myuser/.local/share/virtualenvs/appackager-alt-BgAWFjt5, clear=False, no_vcs_ignore=False, global=False)
    seeder FromAppData(download=False, pip=bundle, setuptools=bundle, wheel=bundle, via=copy, app_data_dir=/home/myuser/.local/share/virtualenv)
      added seed packages: pip==24.0, setuptools==69.1.0, wheel==0.42.0
    activators BashActivator,CShellActivator,FishActivator,NushellActivator,PowerShellActivator,PythonActivator

  ✔ Successfully created virtual environment!
  Virtualenv location: /home/myuser/.local/share/virtualenvs/appackager-alt-BgAWFjt5
  preparing to excise: []
  extracted local package name 'kt.appackager' using setup.py
  dpkg-deb: building package 'appackager' in 'appackager_0.9.0-1_all.deb'.

The Debian package we just built can be installed in the system to build
further installation packages, so we can discard our scratch worktree at this
point:

.. code-block:: shell-session

  $ sudo dpkg -i packages/appackager_0.9.0-1_all.deb
  Selecting previously unselected package appackager.
  (Reading database ... 539696 files and directories currently installed.)
  Preparing to unpack .../appackager_0.9.0-1_all.deb ...
  Unpacking appackager (0.9.0-1) ...
  Setting up appackager (0.9.0-1) ...
  $ cd ../appackager
  $ rm -rf ../appackager-alt
  $ git worktree prune

Now that |appackager| is installed, the installed copy can be used to build
additional |appackager| packages, which can then be used to update the
installation.

.. note::

    In this case, the old appackager won't actually be using any changes made
    in the working copy of the code; you'll need to build again for the
    resulting package to reflect any changes in how the package is
    constructed.


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


.. |appackager| replace:: **appackager**
.. |pipenv| replace:: **pipenv**
.. |pipx| replace:: **pipx**

.. _issue 6054: https://github.com/pypa/pipenv/issues/6054
.. _pipenv: https://pipenv.pypa.io/en/latest/
.. _pipx: https://pypa.github.io/pipx/
.. _python-deb-packages: https://github.com/freddrake/python-deb-packages
