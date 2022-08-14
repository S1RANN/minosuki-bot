from sqlalchemy import create_engine, Column, Integer, String, select
from sqlalchemy.orm import sessionmaker, mapped_column, DeclarativeBase

# 创建数据库连接
engine = create_engine('sqlite:///gpt_log.db', echo=True)

class Base(DeclarativeBase):
    pass
# 定义User类
class ChatLog(Base):
    __tablename__ = 'chatLogs'
    id = mapped_column(Integer(), primary_key=True, autoincrement=True)
    user_id = Column(String(50))
    role = Column(String(10))
    content = Column(String(2000))

    def __repr__(self):
        return "<User(user_id='%s', role='%s', content='%s')>" % (
                                self.user_id, self.role, self.content)

# 创建表格
# Base.metadata.create_all(engine)
log_table = ChatLog.__table__
with engine.begin() as conn:
    stmt = select(log_table).where(log_table.c.user_id == 5389980251).order_by(log_table.c.id.desc())
    for row in conn.execute(stmt):
        print(row)