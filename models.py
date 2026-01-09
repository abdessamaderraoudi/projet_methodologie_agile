from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(20)) # 'professeur' ou 'chef'

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True, index=True)
    type_inc = Column(String(100)) # Ex: Videoprojecteur
    salle = Column(String(50))
    description = Column(String(255))
    statut = Column(String(50), default="En attente") # En cours, Terminé
    date_creation = Column(DateTime, default=datetime.datetime.utcnow)
    prof_id = Column(Integer, ForeignKey("users.id"))