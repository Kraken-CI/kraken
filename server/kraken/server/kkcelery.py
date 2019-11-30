#!/usr/bin/env python3
from kraken.server.bg.clry import app

def main():
    argv = [
        'worker',
        '--loglevel=INFO',
    ]
    app.worker_main(argv=argv)


if __name__ == "__main__":
    main()
