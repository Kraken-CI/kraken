import os
import alembic.config

here = os.path.dirname(os.path.abspath(__file__))

alembic_args = [
    '-c', os.path.join(here, 'alembic.ini'),
    'upgrade', 'head'
]


def main():
    alembic.config.main(argv=alembic_args)


if __name__ == "__main__":
    main()
