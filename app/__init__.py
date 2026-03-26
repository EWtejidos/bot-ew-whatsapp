from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from .config import load_configurations, configure_logging
from sqlalchemy import text
import os
import secrets

# --- INICIALIZACIÓN DE EXTENSIONES ---
# db: El motor que conecta Flask con tu archivo usuarios.db
db = SQLAlchemy()
# login_manager: El "portero" que vigila quién tiene sesión iniciada
login_manager = LoginManager()
from .models import User

def create_app():
    from .views import webhook_blueprint

    # Ruta absoluta hacia tu carpeta de archivos web (HTML/CSS/Images)
    base_dir = '/home/ewtejidos/bot/ew_website'

    app = Flask(__name__,
                template_folder=base_dir,
                static_folder=base_dir,
                static_url_path='')

    # --- CONFIGURACIÓN DEL SISTEMA ---
    # Ubicación del archivo de base de datos dentro de la carpeta 'app'
    path_db = os.path.join(os.path.dirname(__file__), 'usuarios.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{path_db}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Llave de seguridad para encriptar las cookies de sesión
    app.config['SECRET_KEY'] = 'FEFE1111.'

    # Inicializar las extensiones vinculándolas a esta aplicación específica
    db.init_app(app)
    login_manager.init_app(app)
    # Si alguien intenta entrar a una página privada sin loguearse, lo mandamos aquí:
    login_manager.login_view = 'show_page'

    load_configurations(app)
    configure_logging()

    # Función que usa Flask-Login para recuperar el usuario de la DB mediante su ID
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- RUTAS DE NAVEGACIÓN ---

    @app.route('/')
    def home():
        return render_template('index.html')

    # Lógica del Login: Recibe los datos del formulario POST
    @app.route('/login', methods=['POST'])
    def login_post():
        # Capturamos los datos enviados desde el HTML (name="...")
        user_type = request.form.get('user_type')
        username = request.form.get('username')
        password = request.form.get('password')

        # Buscamos al usuario por su nombre en la base de datos
        user = User.query.filter_by(username=username).first()

        # Verificamos si el usuario existe y si la contraseña (hash) coincide
        if user and check_password_hash(user.password, password):
            # Creamos la sesión oficial del usuario
            login_user(user)

            # REDIRECCIÓN SEGÚN EL TIPO ELEGIDO EN EL FORMULARIO
            if user_type == 'admin':
                return redirect(url_for('show_page', page='tableroadmin'))
            elif user_type == 'transportista':
                return redirect(url_for('show_page', page='transporteadmin')) # O la página que gustes
            else:
                # Por defecto (Tejedor/Aliado) va al tablero normal
                return redirect(url_for('show_page', page='dashboard'))

        # Si algo falla (usuario no existe o clave mal), enviamos el mensaje de error
        flash('Usuario o contraseña incorrectos')
        # Lo regresamos a la página de login (pasando 'loguin' como parámetro)
        return redirect(url_for('show_page', page='loguin'))

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('home'))

    # Manejador dinámico de todas tus páginas HTML
    @app.route('/<page>')
    def show_page(page):
        # Limpiamos el nombre por si escriben "contacto.html" en la URL
        clean_page = page.replace('.html', '')

        # Diccionario maestro de rutas de Ethereal Whisper
        pages = {
            'aliados': 'aliados.html',
            'loguin': 'loguin.html',
            'productos': 'productos.html',
            'pedidos': 'pedidos.html',
            'politicas': 'politicas.html',
            'nosotros': 'sobre-nosotros.html',
            'dashboard': 'dashboard.html',
            'tableroadmin': 'tableroadmin.html',
            'anticiposadmin': 'anticiposadmin.html',
            'ordenesadmin': 'ordenesadmin.html',
            'transporteadmin': 'transporteadmin.html',
            'contabilidadadmin': 'contabilidadadmin.html',
            'basesadmin': 'basesadmin.html'
        }

        template = pages.get(clean_page)

        if template:
            # --- PROTECCIÓN DE SEGURIDAD ---
            # Definimos qué páginas NO se pueden ver sin haber iniciado sesión
            paginas_privadas = [
                'dashboard', 'pedidos', 'productos',
                'tableroadmin', 'anticiposadmin', 'ordenesadmin',
                'transporteadmin', 'contabilidadadmin', 'basesadmin'
            ]

            if clean_page in paginas_privadas:
                # Si la página es privada y el usuario no está logueado...
                if not current_user.is_authenticated:
                    # Lo rebotamos al login
                    return redirect(url_for('show_page', page='loguin'))

            # Si pasó la prueba o la página es pública (como 'nosotros'), la mostramos
            return render_template(template)

        # Si la página no está en el diccionario, error 404
        return f"La página '{page}' no existe", 404

    # Registro del Blueprint del bot de WhatsApp
    app.register_blueprint(webhook_blueprint)

    with app.app_context():
        db.create_all()
        ensure_runtime_schema()

    return app


def ensure_runtime_schema():
    inspector = db.inspect(db.engine)

    if not inspector.has_table("customer"):
        db.create_all()

    if not inspector.has_table("order"):
        db.create_all()
        return

    order_columns = {column["name"] for column in inspector.get_columns("order")}
    customer_columns = (
        {column["name"] for column in inspector.get_columns("customer")}
        if inspector.has_table("customer")
        else set()
    )

    statements = []

    if "order_code" not in order_columns:
        statements.append("ALTER TABLE \"order\" ADD COLUMN order_code VARCHAR(20)")
    if "id_orden" not in order_columns:
        statements.append("ALTER TABLE \"order\" ADD COLUMN id_orden VARCHAR(24)")
    if "customer_id" not in order_columns:
        statements.append("ALTER TABLE \"order\" ADD COLUMN customer_id INTEGER")
    if "date" not in order_columns:
        statements.append("ALTER TABLE \"order\" ADD COLUMN date VARCHAR(20)")
    if "deadline" not in order_columns:
        statements.append("ALTER TABLE \"order\" ADD COLUMN deadline VARCHAR(80)")
    if "quote_min" not in order_columns:
        statements.append("ALTER TABLE \"order\" ADD COLUMN quote_min INTEGER")
    if "quote_max" not in order_columns:
        statements.append("ALTER TABLE \"order\" ADD COLUMN quote_max INTEGER")
    if "advance_payment" not in order_columns:
        statements.append("ALTER TABLE \"order\" ADD COLUMN advance_payment INTEGER")
    if "payment_received_at" not in order_columns:
        statements.append("ALTER TABLE \"order\" ADD COLUMN payment_received_at DATETIME")

    if inspector.has_table("customer"):
        if "created_at" not in customer_columns:
            statements.append("ALTER TABLE customer ADD COLUMN created_at DATETIME")
        if "updated_at" not in customer_columns:
            statements.append("ALTER TABLE customer ADD COLUMN updated_at DATETIME")

    for statement in statements:
        db.session.execute(text(statement))

    if statements:
        db.session.commit()

    if inspector.has_table("order"):
        rows_without_order_id = db.session.execute(
            text("SELECT id FROM \"order\" WHERE id_orden IS NULL OR TRIM(id_orden) = ''")
        ).fetchall()
        for row in rows_without_order_id:
            db.session.execute(
                text("UPDATE \"order\" SET id_orden = :id_orden WHERE id = :id"),
                {"id_orden": f"ID-{row.id:06d}-{secrets.token_hex(2).upper()}", "id": row.id},
            )

        rows_without_date = db.session.execute(
            text("SELECT id FROM \"order\" WHERE date IS NULL OR TRIM(date) = ''")
        ).fetchall()
        for row in rows_without_date:
            db.session.execute(
                text("UPDATE \"order\" SET date = strftime('%d/%m/%Y %H:%M', created_at) WHERE id = :id"),
                {"id": row.id},
            )

        if rows_without_order_id or rows_without_date:
            db.session.commit()
