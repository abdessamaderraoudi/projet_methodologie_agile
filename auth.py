import bcrypt

def get_password_hash(password: str):
    """Hash un mot de passe avec bcrypt"""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Retourner en string UTF-8
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str):
    """Vérifie si le mot de passe correspond au hash"""
    try:
        password_byte = plain_password.encode('utf-8')
        hashed_byte = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_byte, hashed_byte)
    except Exception as e:
        print(f"Erreur de vérification: {e}")
        return False