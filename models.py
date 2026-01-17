from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Departement(Base):
    __tablename__ = "departements"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), unique=True, index=True)  # Ex: Informatique, Mathématiques, Physique
    code = Column(String(10), unique=True)  # Ex: INFO, MATH, PHY
    
    # Relations
    professeurs = relationship("User", back_populates="departement", foreign_keys="User.departement_id")
    chef = relationship("User", back_populates="departement_chef", foreign_keys="User.chef_departement_id", uselist=False)
    incidents = relationship("Incident", back_populates="departement")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(20))  # 'professeur' ou 'chef'
    nom_complet = Column(String(100))
    email = Column(String(100), unique=True)
    
    # Relations avec département
    departement_id = Column(Integer, ForeignKey("departements.id"), nullable=True)
    departement = relationship("Departement", back_populates="professeurs", foreign_keys=[departement_id])
    
    # Si c'est un chef de département
    chef_departement_id = Column(Integer, ForeignKey("departements.id"), nullable=True)
    departement_chef = relationship("Departement", back_populates="chef", foreign_keys=[chef_departement_id])
    
    # Incidents créés par ce professeur
    incidents = relationship("Incident", back_populates="professeur", foreign_keys="Incident.prof_id")

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True, index=True)
    type_inc = Column(String(100))  # Ex: Videoprojecteur, Climatisation, Ordinateur
    salle = Column(String(50))
    description = Column(String(500))
    image_path = Column(String(255), nullable=True)  # Chemin vers l'image
    statut = Column(String(50), default="En attente")  # En attente, En cours, Terminé
    date_creation = Column(DateTime, default=datetime.datetime.utcnow)
    date_modification = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relations
    prof_id = Column(Integer, ForeignKey("users.id"))
    professeur = relationship("User", back_populates="incidents", foreign_keys=[prof_id])
    
    departement_id = Column(Integer, ForeignKey("departements.id"))
    departement = relationship("Departement", back_populates="incidents")
    
    # Commentaires du chef (optionnel)
    commentaire_chef = Column(String(500), nullable=True)