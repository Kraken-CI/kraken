#!/usr/bin/env python3
import os

from kraken.server.bg.clry import app
from . import srvcheck
from . import consts


def main():
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
    srvcheck.check_url('planner', planner_url, 7997)

    argv = [
        'worker',
        '--loglevel=INFO',
    ]
    app.worker_main(argv=argv)


if __name__ == "__main__":
    main()
