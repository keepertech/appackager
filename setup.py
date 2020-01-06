"""Keeper Technology File Analytics Service"""

import setuptools

NAME = 'kt.appackager'
VERSION = '0.2.0'
LICENSE = '''\
(c) 2019.  Keeper Technology LLC.  All Rights Reserved.
Use is subject to license.  Reproduction and distribution is strictly
prohibited.

Subject to the following third party software licenses and terms and
conditions (including open source):  www.keepertech.com/thirdpartylicenses
'''

# The tests package is only for local use; do not install.
package_dir = 'src'
packages = [p for p in setuptools.find_packages(package_dir)]


def script(name, relentry):
    if ':' not in relentry:
        relentry += ':main'
    return '%s = %s.%s' % (name, NAME, relentry)


metadata = dict(
    name=NAME,
    version=VERSION,
    license=LICENSE,
    author='Keeper Technology, LLC',
    author_email='info@keepertech.com',
    url='http://kt-git.keepertech.com/DevTools/kt.appackager',
    description=__doc__,
    packages=packages,
    package_dir={'': package_dir},
    namespace_packages=['kt'],
    include_package_data=True,
    install_requires=[
        'toml',
        'wheel',
    ],
    entry_points={
        'console_scripts': [
            'appackage = kt.appackager.build:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)


# We rely on only running this as a script when __name__ is '__main__',
# since mkscripts.py imports this as a module to get entry-point
# information.
#
if __name__ == '__main__':
    setuptools.setup(**metadata)
