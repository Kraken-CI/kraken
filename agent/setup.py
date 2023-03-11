#!/usr/bin/env python3
import os
from setuptools import setup, find_packages

setup(
    name='kraken-agent',
    version=os.environ['KRAKEN_VERSION'],
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'kkagent = kraken.agent.main:main',
            'kktool = kraken.agent.tool:main',
        ],
        'kraken.tools': [
            'git = kraken.agent.kraken_git',
            'pytest = kraken.agent.kraken_pytest',
            'rndtest = kraken.agent.kraken_rndtest',
            'shell = kraken.agent.kraken_shell',
            'pylint = kraken.agent.kraken_pylint',
            'cloc = kraken.agent.kraken_cloc',
            'nglint = kraken.agent.kraken_nglint',
            'artifacts = kraken.agent.kraken_artifacts',
            'cache = kraken.agent.kraken_cache',
            'gotest = kraken.agent.kraken_gotest',
            'junit_collect = kraken.agent.kraken_junit_collect',
            'values_collect = kraken.agent.kraken_values_collect',
            'data = kraken.agent.kraken_data',
        ]
    },
)
