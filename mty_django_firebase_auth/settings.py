# -*- coding: utf-8 -*-
""" Configuración de settings para la aplicación mty_django_firebase_auth """
import os
from django.conf import settings
from rest_framework.settings import APISettings
from .utils import map_firebase_uid_to_username


DEFAULTS = {
    # path to JSON file with firebase app config
    'FIREBASE_APP_CONFIG_KEY': os.getenv('FIREBASE_APP_CONFIG_KEY', ''),
    # Permitir la creación de un nuevo usuario local en la base de datos
    'FIREBASE_CREATE_LOCAL_USER': os.getenv('FIREBASE_CREATE_LOCAL_USER', True),
    # Intentar dividir el nombre de usuario de firebase y establecer el nombre y apellido del usuario local
    'FIREBASE_ATTEMPT_CREATE_WITH_DISPLAY_NAME': os.getenv('FIREBASE_ATTEMPT_CREATE_WITH_DISPLAY_NAME', False),
    # Prefijo del encabezado de autorización, usualmente JWT o Bearer (v.gr. Bearer <token>)
    'FIREBASE_AUTH_HEADER_PREFIX': os.getenv('FIREBASE_AUTH_HEADER_PREFIX', 'Bearer'),
    # Verificar que el JWT no haya sido revocado
    'FIREBASE_CHECK_JWT_REVOKED': os.getenv('FIREBASE_CHECK_JWT_REVOKED', True),
    # Requerir que el usuario de firebase tenga el correo verificado
    'FIREBASE_AUTH_EMAIL_VERIFICATION': os.getenv('FIREBASE_AUTH_EMAIL_VERIFICATION', False),
    # Función de mapeo de uid de firebase con username de django.
    # La función debe aceptar firebase_admin.auth.UserRecord como argumento y devolver str
    'FIREBASE_USERNAME_MAPPING_FUNC': map_firebase_uid_to_username
}

USER_SETTINGS = os.getenv('MTY_FIREBASE_AUTH', getattr(settings, 'MTY_FIREBASE_AUTH', None))

# Lista de configuraciones que pueden estar en notación de importación de cadena.
IMPORT_STRINGS = ()

api_settings = APISettings(USER_SETTINGS, DEFAULTS, IMPORT_STRINGS)
