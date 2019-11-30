#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name='kraken-server',
    version='0.0.1',
    packages=find_packages(),
    package_data={
        'kraken.server': ['swagger.yml'],
    },
    entry_points={
        'console_scripts': [
            'kkserver = kraken.server.server:main',
            'kkscheduler = kraken.server.scheduler:main',
            'kkplanner = kraken.server.planner:main',
            'kkcelery = kraken.server.kkcelery:main',
        ],
    },
)
