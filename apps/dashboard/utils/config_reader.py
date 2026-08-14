import configparser
from django.conf import settings

CONFIG_PATH = settings.CONFIG_INI_PATH

def read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH, encoding='utf-8')
    return config

def write_config(section, key, value):
    config = read_config()
    if section not in config:
        config.add_section(section)
    config.set(section, key, str(value))
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        config.write(f)

def get_all_sections():
    config = read_config()
    return {section: dict(config.items(section)) for section in config.sections()}