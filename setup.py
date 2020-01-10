"""Keeper Technology File Analytics Service"""

NAME = 'kt.appackager'
VERSION = '0.2.0'
LICENSE = 'file: LICENSE.txt'


metadata = dict(
    name=NAME,
    version=VERSION,
    license=LICENSE,
    author='Keeper Technology, LLC',
    author_email='info@keepertech.com',
    url='http://kt-git.keepertech.com/DevTools/kt.appackager',
    description=__doc__,
    packages=['kt.appackager'],
    package_dir={'': 'src'},
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


if __name__ == '__main__':
    import setuptools
    setuptools.setup(**metadata)
