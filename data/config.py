import os
import pymongo
from utils.logger import logger
import secrets
import platform


class Constants:
    # Version info
    VERSION = "0.0.1"
    ADMIN = "chiro"
    EMAIL = "Chiro2001@163.com"
    # Environment
    ENVIRONMENT = os.environ.get("ENV") if os.environ.get("ENV") is not None else (
        "release" if platform.system() == 'Linux' else "dev")
    # Database
    FIND_LIMIT = 30
    DATABASE_URI = ''
    DATABASE_NAME = 'globecom'
    RUN_REBASE = False


class Statics:
    pass


class Config:
    def __init__(self):
        self.data_default = {
            "version": Constants.VERSION,
        }
        self.data = self.data_default


config = Config()
