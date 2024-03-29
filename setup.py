"""Application packaging for Debian-based distributions."""

NAME = 'kt.appackager'
VERSION = '0.7.0'
LICENSE = 'file: LICENSE.rst'


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
    include_package_data=True,
    install_requires=[
        'tomli',
        'wheel',
    ],
    entry_points={
        'console_scripts': [
            'appackage = kt.appackager.build:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)


if __name__ == '__main__':
    import setuptools
    setuptools.setup(**metadata)
