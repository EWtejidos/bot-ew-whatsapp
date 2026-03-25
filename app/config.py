import sys
import os
import logging

def load_configurations(app):
    # Ya NO usamos load_dotenv() porque los tokens vienen del WSGI
    # Simplemente pasamos lo que hay en el sistema a la configuración de Flask
    app.config.update(
        ACCESS_TOKEN=os.environ.get("ACCESS_TOKEN"),
        YOUR_PHONE_NUMBER=os.environ.get("YOUR_PHONE_NUMBER"),
        APP_ID=os.environ.get("APP_ID"),
        APP_SECRET=os.environ.get("APP_SECRET"),
        RECIPIENT_WAID=os.environ.get("RECIPIENT_WAID"),
        VERSION=os.environ.get("VERSION", "v18.0"),
        PHONE_NUMBER_ID=os.environ.get("PHONE_NUMBER_ID"),
        VERIFY_TOKEN=os.environ.get("VERIFY_TOKEN")
    )

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
