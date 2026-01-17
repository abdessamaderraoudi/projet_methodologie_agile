import database
import models
import auth
from sqlalchemy.orm import Session

def test_login():
    """Teste la connexion avec les utilisateurs existants"""
    db = database.SessionLocal()
    
    print("=== Test des utilisateurs ===\n")
    
    # Récupérer tous les utilisateurs
    users = db.query(models.User).all()
    
    if not users:
        print("❌ Aucun utilisateur trouvé dans la base de données")
        db.close()
        return
    
    print(f"✅ {len(users)} utilisateur(s) trouvé(s)\n")
    
    for user in users:
        print(f"Username: {user.username}")
        print(f"Role: {user.role}")
        print(f"Hash: {user.hashed_password[:50]}...")
        
        # Tester avec le mot de passe "123"
        test_password = "123"
        result = auth.verify_password(test_password, user.hashed_password)
        
        if result:
            print(f"✅ Mot de passe '{test_password}' fonctionne!\n")
        else:
            print(f"❌ Mot de passe '{test_password}' ne fonctionne pas\n")
    
    db.close()

def reset_users():
    """Réinitialise les utilisateurs avec des mots de passe hashés corrects"""
    db = database.SessionLocal()
    
    print("=== Réinitialisation des utilisateurs ===\n")
    
    # Supprimer tous les utilisateurs existants
    db.query(models.User).delete()
    db.query(models.Incident).delete()
    db.commit()
    
    # Créer les départements s'ils n'existent pas
    dept_info = db.query(models.Departement).filter(models.Departement.code == "INFO").first()
    if not dept_info:
        dept_info = models.Departement(nom="Informatique", code="INFO")
        db.add(dept_info)
        db.commit()
        db.refresh(dept_info)
    
    # Créer un professeur
    prof_hash = auth.get_password_hash("123")
    prof = models.User(
        username="prof1",
        hashed_password=prof_hash,
        role="professeur",
        nom_complet="Professeur Test",
        email="prof1@fstt.ac.ma",
        departement_id=dept_info.id
    )
    
    # Créer un chef
    chef_hash = auth.get_password_hash("123")
    chef = models.User(
        username="chef1",
        hashed_password=chef_hash,
        role="chef",
        nom_complet="Chef Département Info",
        email="chef1@fstt.ac.ma",
        chef_departement_id=dept_info.id
    )
    
    db.add_all([prof, chef])
    db.commit()
    
    print("✅ Utilisateurs créés avec succès:")
    print(f"   - Username: prof1, Password: 123, Role: professeur")
    print(f"   - Username: chef1, Password: 123, Role: chef")
    print(f"\n✅ Hash prof1: {prof_hash[:50]}...")
    print(f"✅ Hash chef1: {chef_hash[:50]}...")
    
    db.close()

if __name__ == "__main__":
    print("1. Tester les utilisateurs existants")
    print("2. Réinitialiser les utilisateurs")
    choice = input("\nChoisissez une option (1 ou 2): ")
    
    if choice == "1":
        test_login()
    elif choice == "2":
        confirm = input("⚠️  Cela va supprimer tous les utilisateurs existants. Continuer? (oui/non): ")
        if confirm.lower() == "oui":
            reset_users()
            print("\n--- Test après réinitialisation ---")
            test_login()
        else:
            print("Opération annulée")
    else:
        print("Option invalide")