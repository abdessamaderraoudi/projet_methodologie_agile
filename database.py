from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Modifiez les accès selon votre config MySQL
# Format sans mot de passe : mysql+pymysql://root@localhost/fstt_incidents
URL_DATABASE = "mysql+pymysql://root@localhost/fstt_incidents"

engine = create_engine(URL_DATABASE)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()