from fastapi import FastAPI, Depends, Form, Request, HTTPException, Response, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import models, database, auth
from datetime import datetime, timedelta
import secrets
import uuid
import os
import shutil
from pathlib import Path

app = FastAPI()
models.Base.metadata.create_all(bind=database.engine)
templates = Jinja2Templates(directory="templates")

# Créer les dossiers nécessaires
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Créer le dossier static pour les fichiers statiques (CSS, JS, images)
STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")



# Stockage des sessions actives
active_sessions = {}

def add_no_cache_headers(response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

def create_session_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    active_sessions[token] = {
        "user_id": user_id,
        "created_at": datetime.now(),
        "page_token": None
    }
    return token

def create_page_token(session_token: str) -> str:
    page_token = str(uuid.uuid4())
    if session_token in active_sessions:
        active_sessions[session_token]["page_token"] = page_token
    return page_token

def validate_session(request: Request, expected_user_id: int) -> tuple:
    session_token = request.cookies.get("session_token")
    if not session_token or session_token not in active_sessions:
        return False, None
    
    session_data = active_sessions[session_token]
    if session_data["user_id"] != expected_user_id:
        return False, None
    
    if datetime.now() - session_data["created_at"] > timedelta(hours=24):
        del active_sessions[session_token]
        return False, None
    
    return True, session_token

def invalidate_session(session_token: str):
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]

async def save_upload_file(upload_file: UploadFile) -> str:
    """Sauvegarde le fichier uploadé et retourne le chemin"""
    if not upload_file:
        return None
    
    # Générer un nom unique
    file_extension = upload_file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    
    # Sauvegarder le fichier
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    
    return f"/uploads/{unique_filename}"

# --- AUTHENTIFICATION ---
@app.get("/favicon.ico")
async def favicon():
    """Route pour le favicon"""
    favicon_path = STATIC_DIR / "favicon.ico"
    if favicon_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(favicon_path)
    else:
        # Retourner une réponse vide si le favicon n'existe pas
        return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        invalidate_session(session_token)
    
    response = templates.TemplateResponse("login.html", {"request": request})
    response.delete_cookie("session_token")
    return add_no_cache_headers(response)

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    
    # Debug
    if user:
        print(f"✅ Utilisateur trouvé: {user.username}")
        print(f"Hash en base: {user.hashed_password[:50]}...")
        is_valid = auth.verify_password(password, user.hashed_password)
        print(f"Vérification mot de passe: {is_valid}")
    else:
        print(f"❌ Utilisateur '{username}' non trouvé")
    
    if not user or not auth.verify_password(password, user.hashed_password):
        response = RedirectResponse(url="/?error=1", status_code=303)
        return add_no_cache_headers(response)
    
    session_token = create_session_token(user.id)
    
    if user.role == "chef":
        response = RedirectResponse(url=f"/admin/{user.id}", status_code=303)
    else:
        response = RedirectResponse(url=f"/prof/{user.id}", status_code=303)
    
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        samesite="strict",
        max_age=86400
    )
    return add_no_cache_headers(response)

@app.get("/logout")
def logout(request: Request):
    session_token = request.cookies.get("session_token")
    invalidate_session(session_token)
    
    response = RedirectResponse(url="/logout-complete", status_code=303)
    response.delete_cookie("session_token")
    return add_no_cache_headers(response)

@app.get("/logout-complete", response_class=HTMLResponse)
def logout_complete(request: Request):
    response = templates.TemplateResponse("logout_complete.html", {"request": request})
    return add_no_cache_headers(response)

@app.get("/check-session/{user_id}")
def check_session(request: Request, user_id: int):
    is_valid, _ = validate_session(request, user_id)
    if not is_valid:
        return JSONResponse({"valid": False}, status_code=401)
    return JSONResponse({"valid": True})

# --- ESPACE PROFESSEUR ---
@app.get("/prof/{user_id}", response_class=HTMLResponse)
def prof_dashboard(request: Request, user_id: int, db: Session = Depends(database.get_db)):
    is_valid, session_token = validate_session(request, user_id)
    if not is_valid:
        response = RedirectResponse(url="/", status_code=303)
        return add_no_cache_headers(response)
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.role not in ["professeur", "prof"]:
        response = RedirectResponse(url="/", status_code=303)
        return add_no_cache_headers(response)

    page_token = create_page_token(session_token)
    
    # Récupérer les incidents du professeur
    my_incidents = db.query(models.Incident).filter(
        models.Incident.prof_id == user_id
    ).order_by(models.Incident.date_creation.desc()).all()
    
    response = templates.TemplateResponse("prof.html", {
        "request": request,
        "incidents": my_incidents,
        "user": user,
        "user_id": user_id,
        "page_token": page_token
    })
    return add_no_cache_headers(response)

@app.post("/prof/signaler/{user_id}")
async def add_incident(
    request: Request, 
    user_id: int, 
    type_inc: str = Form(...), 
    salle: str = Form(...), 
    desc: str = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(database.get_db)
):
    is_valid, _ = validate_session(request, user_id)
    if not is_valid:
        return RedirectResponse(url="/", status_code=303)
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.departement_id:
        raise HTTPException(status_code=400, detail="Professeur sans département")
    
    # Sauvegarder l'image si elle existe
    image_path = None
    if image and image.filename:
        image_path = await save_upload_file(image)
    
    new_inc = models.Incident(
        type_inc=type_inc, 
        salle=salle, 
        description=desc, 
        prof_id=user_id,
        departement_id=user.departement_id,
        image_path=image_path
    )
    db.add(new_inc)
    db.commit()
    return RedirectResponse(url=f"/prof/{user_id}", status_code=303)

# --- ESPACE CHEF DE DEPARTEMENT ---
@app.get("/admin/{user_id}", response_class=HTMLResponse)
def admin_dashboard(request: Request, user_id: int, db: Session = Depends(database.get_db)):
    is_valid, session_token = validate_session(request, user_id)
    if not is_valid:
        response = RedirectResponse(url="/", status_code=303)
        return add_no_cache_headers(response)
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.role != "chef":
        response = RedirectResponse(url="/", status_code=303)
        return add_no_cache_headers(response)

    page_token = create_page_token(session_token)
    
    # Récupérer uniquement les incidents du département du chef
    incidents_departement = db.query(models.Incident).filter(
        models.Incident.departement_id == user.chef_departement_id
    ).order_by(models.Incident.date_creation.desc()).all()
    
    response = templates.TemplateResponse("admin.html", {
        "request": request,
        "incidents": incidents_departement,
        "user": user,
        "user_id": user_id,
        "page_token": page_token
    })
    return add_no_cache_headers(response)

@app.post("/admin/update/{inc_id}")
def update_status(
    request: Request, 
    inc_id: int, 
    new_status: str = Form(...), 
    admin_id: int = Form(...),
    commentaire: str = Form(None),
    db: Session = Depends(database.get_db)
):
    is_valid, _ = validate_session(request, admin_id)
    if not is_valid:
        return RedirectResponse(url="/", status_code=303)
    
    user = db.query(models.User).filter(models.User.id == admin_id).first()
    if not user or user.role != "chef":
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    inc = db.query(models.Incident).filter(models.Incident.id == inc_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident non trouvé")
    
    # Vérifier que l'incident appartient au département du chef
    if inc.departement_id != user.chef_departement_id:
        raise HTTPException(status_code=403, detail="Cet incident n'appartient pas à votre département")
    
    inc.statut = new_status
    if commentaire:
        inc.commentaire_chef = commentaire
    db.commit()
    return RedirectResponse(url=f"/admin/{admin_id}", status_code=303)

# --- INSCRIPTION ---
@app.get("/register", response_class=HTMLResponse)
def get_register_page(request: Request, db: Session = Depends(database.get_db)):
    departements = db.query(models.Departement).all()
    response = templates.TemplateResponse("register.html", {
        "request": request,
        "departements": departements
    })
    return add_no_cache_headers(response)

@app.post("/register")
async def register(
    username: str = Form(...), 
    password: str = Form(...), 
    role: str = Form(...),
    nom_complet: str = Form(...),
    email: str = Form(...),
    departement_id: int = Form(...),
    db: Session = Depends(database.get_db)
):
    existing_user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == email)
    ).first()
    if existing_user:
        return RedirectResponse(url="/register?error=exists", status_code=303)
    
    hashed_pwd = auth.get_password_hash(password)
    
    if role == "chef":
        # Vérifier qu'il n'y a pas déjà un chef pour ce département
        existing_chef = db.query(models.User).filter(
            models.User.chef_departement_id == departement_id,
            models.User.role == "chef"
        ).first()
        if existing_chef:
            return RedirectResponse(url="/register?error=chef_exists", status_code=303)
        
        new_user = models.User(
            username=username, 
            hashed_password=hashed_pwd, 
            role=role,
            nom_complet=nom_complet,
            email=email,
            chef_departement_id=departement_id
        )
    else:
        new_user = models.User(
            username=username, 
            hashed_password=hashed_pwd, 
            role=role,
            nom_complet=nom_complet,
            email=email,
            departement_id=departement_id
        )
    
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

# --- INITIALISATION ---
@app.on_event("startup")
def startup_db_setup():
    db = database.SessionLocal()
    
    # Créer les départements s'ils n'existent pas
    if not db.query(models.Departement).first():
        dept_info = models.Departement(nom="Informatique", code="INFO")
        dept_math = models.Departement(nom="Mathématiques", code="MATH")
        dept_phy = models.Departement(nom="Physique", code="PHY")
        dept_chi = models.Departement(nom="Chimie", code="CHI")
        db.add_all([dept_info, dept_math, dept_phy, dept_chi])
        db.commit()
    
    # Créer des utilisateurs de test
    if not db.query(models.User).first():
        dept_info = db.query(models.Departement).filter(models.Departement.code == "INFO").first()
        
        p = models.User(
            username="prof1", 
            hashed_password=auth.get_password_hash("123"), 
            role="professeur",
            nom_complet="Professeur Test",
            email="prof1@fstt.ac.ma",
            departement_id=dept_info.id
        )
        c = models.User(
            username="chef1", 
            hashed_password=auth.get_password_hash("123"), 
            role="chef",
            nom_complet="Chef Département Info",
            email="chef1@fstt.ac.ma",
            chef_departement_id=dept_info.id
        )
        db.add_all([p, c])
        db.commit()
    db.close()

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response