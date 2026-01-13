import pymysql

class DBMySQL:
    def __init__(self, **config):
        self.conn = pymysql.connect(
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            **config
        )

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


