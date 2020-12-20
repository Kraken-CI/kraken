#!/usr/bin/env python3
import os
from setuptools import setup, find_packages

setup(
    name='kraken-server',
    version=os.environ['KRAKEN_VERSION'],
    packages=find_packages(),
    package_data={
        'kraken.server': ['swagger.yml'],
        'migrations': ['alembic.ini'],
    },
    entry_points={
        'console_scripts': [
            'kkserver = kraken.server.server:main',
            'kkscheduler = kraken.server.scheduler:main',
            'kkplanner = kraken.server.planner:main',
            'kkwatchdog = kraken.server.watchdog:main',
            'kkcelery = kraken.server.kkcelery:main',
            'kkdbmigrate = migrations.apply:main',
        ],
    },
)
