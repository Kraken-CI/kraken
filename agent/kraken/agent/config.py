_CFG = {}


def set_config(config):
    global _CFG  # pylint: disable=global-statement
    _CFG = config


def get_config():
    return _CFG


def merge(config):
    global _CFG  # pylint: disable=global-statement

    changes = {}
    for k, v in config.items():
        if k not in _CFG or _CFG[k] != v:
            changes[k] = v
            _CFG[k] = v

    return changes


def get(name):
    return _CFG[name]
