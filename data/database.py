import time
import traceback
import os
from globecom_data import *


class DataBase:
    # 用到的所有数据集合
    COLLECTIONS = [
        'symposium_paper', 'presentations'
    ]

    def __init__(self, dismiss_rebase=False):
        self.client = None
        self.db = None
        self.symposium_paper: SymposiumPaperDB = None
        self.presentations: Presentations = None
        self.presentation_info: PresentationInfo = None
        self.connect_init()
        self.init_parts()
        if Constants.RUN_REBASE:
            self.rebase()

    def init_parts(self):
        self.symposium_paper = SymposiumPaperDB(self.db)
        self.presentations = Presentations(self.db)
        self.presentation_info = PresentationInfo(self.db)

    def rebase(self):
        logger.warning('Rebasing...')
        for col in DataBase.COLLECTIONS:
            # logger.info(f'Dropping {col}')
            self.db[col].drop()
        # # Square 还有自建 Collections
        # for col in SquareDB.recorded_col_name:
        #     self.db[col].drop()
        self.init_parts()
        uid = self.user.update_by_title(Constants.USERS_DEFAULT)
        self.session.update_by_title(uid=uid, password=Constants.USERS_DEFAULT_PASSWORD)

    def connect_init(self):
        if len(Constants.DATABASE_URI) > 0:
            self.client = pymongo.MongoClient(Constants.DATABASE_URI)
        else:
            self.client = pymongo.MongoClient()
        self.db = self.client[Constants.DATABASE_NAME]


db = DataBase()
