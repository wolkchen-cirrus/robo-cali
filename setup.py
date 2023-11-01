from setuptools import setup, find_packages

setup(
    name='robocali',
    version='0.0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pyserial',
        'zaber_motion',
        'prompt_toolkit',
        'asyncio',
        'numpy',
    ],
    entry_points={
        'console_scripts': [
            'robocali = robocali.main:main',
        ],
    },
)

