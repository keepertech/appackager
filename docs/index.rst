appackager
==========

**appackager** supports generation of Debian packages based on a
**pipenv**-based build process and configuration specified in a
project-specific TOML file.

Package versions are determined from **git** tags.  If there are changes
since the last tag that looks like a version number, an alpha version is
assigned based on information maintained in a JSON file in the project's
top-level directory.  Limitations apply:

- If **appackager**'s JSON state is *not* saved under version control,
  separate clones of the repository don't share the same sequence of
  alpha versions.

- If **appackager**'s JSON state *is* saved under version control,
  separate clones still have to be kept up to date, and separate
  branches can easily cause overlapping alpha versions to be generated.

When **appackager** was developed, the intention was that the alpha
versions would only be deployed to per-developer environments, avoiding
the need to coordinate alpha versions across developers.  The JSON state
file was not added to version control.
