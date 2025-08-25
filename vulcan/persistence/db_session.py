from contextlib import contextmanager
from functools import wraps

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base

# Import Configs từ hệ thống cấu hình mới của chúng ta
from vulcan.config.config import Configs

# Xây dựng URL kết nối database từ tệp db_config.yaml
db_config = Configs.db_config.mysql
db_url = (f"mysql+pymysql://{db_config['user']}:{db_config['password']}"
          f"@{db_config['host']}:{db_config['port']}/{db_config['database']}")

# Tạo engine và session
try:
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except ImportError:
    print("Lỗi: Không tìm thấy thư viện 'PyMySQL'. Hãy đảm bảo bạn đã cài đặt nó: pip install PyMySQL")
    engine = None
    SessionLocal = None

Base: DeclarativeMeta = declarative_base()

@contextmanager
def session_scope() -> Session:
    """Context manager used to automatically get Session, avoid errors"""
    if SessionLocal is None:
        raise RuntimeError("Database session is not initialized. Check your PyMySQL installation and DB config.")
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def with_session(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with session_scope() as session:
            return f(session, *args, **kwargs)
    return wrapper


def create_tables():
    """Creates all tables in the database."""
    if engine is None:
        raise RuntimeError("Database engine is not initialized. Cannot create tables.")
    print("Đang tạo các bảng trong database...")
    Base.metadata.create_all(bind=engine)
    print("Tạo bảng thành công.")