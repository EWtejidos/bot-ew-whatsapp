# Importamos 'create_app' para tener acceso a la configuración de tu web (como la ruta de la DB)
# Importamos 'db' para mandar comandos a la base de datos y 'User' para saber qué datos guardar
from app import create_app, db, User

# Importamos esta herramienta vital para convertir la contraseña real en un "Hash" (código cifrado)
from werkzeug.security import generate_password_hash

# Creamos una instancia de tu aplicación. Esto carga las rutas y la configuración de SQLAlchemy
app = create_app()

def add_user(username, password):
    # 'app_context' es como "encender el motor" de Flask sin abrir la página web.
    # Es necesario para que Python sepa en qué base de datos trabajar.
    with app.app_context():
        
        # db.create_all() asegura que el archivo 'usuarios.db' y la tabla 'User' existan.
        # Si ya existen, no hace nada (no borra los datos actuales).
        db.create_all()
        
        # Consultamos si ya existe alguien con ese nombre para no duplicar datos
        if User.query.filter_by(username=username).first():
            print("El usuario ya existe.")
            return
        
        # --- SEGURIDAD ---
        # Convertimos la contraseña "12345" en algo como "pbkdf2:sha256:260000$xyz..."
        # De esta forma, ni tú mismo puedes ver la contraseña real en la base de datos.
        hashed_pw = generate_password_hash(password)
        
        # Creamos el objeto usuario con el nombre y la clave ya cifrada
        new_user = User(username=username, password=hashed_pw)
        
        # 'add' prepara el registro y 'commit' lo guarda permanentemente en el archivo .db
        db.session.add(new_user)
        db.session.commit()
        
        print(f"Usuario {username} creado.")

# Este bloque asegura que el script solo pida datos si lo ejecutas directamente (python3 manage_users.py)
if __name__ == "__main__":
    # Pedimos los datos por consola de forma interactiva
    u = input("Usuario: ")
    p = input("Password: ")
    add_user(u, p)