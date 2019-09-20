_CFG = {}

def set_config(config):
    global _CFG
    _CFG = config

def get_config():
    return _CFG

def merge(config):
    global _CFG
    _CFG.update(config)


def get(name):
    return _CFG[name]
