from data.tools import *
from typing import *


class MultiUpdateDB(BaseDB):
    def __init__(self, d, col_name):
        super().__init__(d, col_name)

    def update(self, data: Union[List[Dict], Dict]):
        if not isinstance(data, list):
            data = [data, ]
        for d in data:
            auto_time_update(self.col, {"title": d.get('title')}, d)

    def find(self, *args, **kwargs):
        return find_many(self.col, *args, **kwargs)


class SymposiumPaperDB(MultiUpdateDB):
    def __init__(self, d):
        super(SymposiumPaperDB, self).__init__(d, 'symposium_paper')


class Presentations(MultiUpdateDB):
    def __init__(self, d):
        super(Presentations, self).__init__(d, 'presentations')
