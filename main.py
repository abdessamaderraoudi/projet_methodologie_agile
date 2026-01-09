from fastapi import FastAPI, Depends, Form, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import models, database, auth
from datetime import datetime, timedelta
import secrets
import uuid

app = FastAPI()
models.Base.metadata.create_all(bind=database.engine)
templates = Jinja2Templates(directory="templates")

# Stockage des sessions actives (en production, utilisez Redis)
active_sessions = {}
# Stockage des pages visitées pour chaque session
session_page_tokens = {}

def add_no_cache_headers(response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, post-check=0, pre-check=0"
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
    """Crée un token unique pour chaque chargement de page"""
    page_token = str(uuid.uuid4())
    if session_token in active_sessions:
        active_sessions[session_token]["page_token"] = page_token
    return page_token

def validate_session(request: Request, expected_user_id: int, check_page_token: bool = False) -> tuple:
    session_token = request.cookies.get("session_token")
    if not session_token or session_token not in active_sessions:
        return False, None
    
    session_data = active_sessions[session_token]
    if session_data["user_id"] != expected_user_id:
        return False, None
    
    # Vérifier que la session n'est pas expirée (24h)
    if datetime.now() - session_data["created_at"] > timedelta(hours=24):
        del active_sessions[session_token]
        return False, None
    
    return True, session_token

def invalidate_session(session_token: str):
    """Invalide complètement une session"""
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]

# --- AUTHENTIFICATION ---
@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    # Si l'utilisateur a déjà une session active, on la détruit
    session_token = request.cookies.get("session_token")
    if session_token:
        invalidate_session(session_token)
    
    response = templates.TemplateResponse("login.html", {"request": request})
    response.delete_cookie("session_token")
    return add_no_cache_headers(response)

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        response = RedirectResponse(url="/?error=1", status_code=303)
        return add_no_cache_headers(response)
    
    # Créer un token de session sécurisé
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
    """Page intermédiaire après déconnexion pour empêcher le retour"""
    response = templates.TemplateResponse("logout_complete.html", {"request": request})
    return add_no_cache_headers(response)

# Endpoint pour vérifier la validité de la session (appelé par JS)
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

    # Créer un nouveau token de page
    page_token = create_page_token(session_token)
    
    my_incidents = db.query(models.Incident).filter(models.Incident.prof_id == user_id).all()
    response = templates.TemplateResponse("prof.html", {
        "request": request,
        "incidents": my_incidents,
        "user_id": user_id,
        "page_token": page_token
    })
    return add_no_cache_headers(response)

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

    # Créer un nouveau token de page
    page_token = create_page_token(session_token)
    
    all_incidents = db.query(models.Incident).all()
    response = templates.TemplateResponse("admin.html", {
        "request": request,
        "incidents": all_incidents,
        "user_id": user_id,
        "page_token": page_token
    })
    return add_no_cache_headers(response)

# --- LE RESTE DES ROUTES ---
@app.get("/register", response_class=HTMLResponse)
def get_register_page(request: Request):
    response = templates.TemplateResponse("register.html", {"request": request})
    return add_no_cache_headers(response)

@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...), role: str = Form(...), db: Session = Depends(database.get_db)):
    existing_user = db.query(models.User).filter(models.User.username == username).first()
    if existing_user:
        return RedirectResponse(url="/register?error=exists", status_code=303)
    
    hashed_pwd = auth.get_password_hash(password)
    new_user = models.User(username=username, hashed_password=hashed_pwd, role=role)
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/prof/signaler/{user_id}")
def add_incident(request: Request, user_id: int, type_inc: str = Form(...), salle: str = Form(...), desc: str = Form(...), db: Session = Depends(database.get_db)):
    is_valid, _ = validate_session(request, user_id)
    if not is_valid:
        return RedirectResponse(url="/", status_code=303)
    
    new_inc = models.Incident(type_inc=type_inc, salle=salle, description=desc, prof_id=user_id)
    db.add(new_inc)
    db.commit()
    return RedirectResponse(url=f"/prof/{user_id}", status_code=303)

@app.post("/admin/update/{inc_id}")
def update_status(request: Request, inc_id: int, new_status: str = Form(...), admin_id: int = Form(...), db: Session = Depends(database.get_db)):
    is_valid, _ = validate_session(request, admin_id)
    if not is_valid:
        return RedirectResponse(url="/", status_code=303)
    
    user = db.query(models.User).filter(models.User.id == admin_id).first()
    if not user or user.role != "chef":
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    inc = db.query(models.Incident).filter(models.Incident.id == inc_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident non trouvé")
    
    inc.statut = new_status
    db.commit()
    return RedirectResponse(url=f"/admin/{admin_id}", status_code=303)

@app.on_event("startup")
def startup_db_setup():
    db = database.SessionLocal()
    if not db.query(models.User).first():
        p = models.User(username="prof1", hashed_password=auth.get_password_hash("123"), role="professeur")
        c = models.User(username="chef1", hashed_password=auth.get_password_hash("123"), role="chef")
        db.add_all([p, c])
        db.commit()
    db.close()

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, post-check=0, pre-check=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response