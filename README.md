# Mty Django Firebase Auth

## Requisitos

* Python 3
* Django 4
* Django Rest Framework 3 

## Instalación

```
$ pip install mty-django-firebase-auth
```

Agregar la aplicación en la sección `INSTALLED_APPS` en `settings.py`.

```python
INSTALLED_APPS = [
    # ...
    'mty_django_firebase_auth',
]
```

En el archivo settings.py, agregar la siguiente configuración en la sección `REST_FRAMEWORK`. Si se desea mantener el acceso al API para usuarios locales, se debe agregar `rest_framework.authentication.SessionAuthentication` también; si además se quiere permitir acceso mediante Basic Authentication hay que mantener `rest_framework.authentication.BasicAuthentication` también.

```python
REST_FRAMEWORK = {
  # ...
  'DEFAULT_AUTHENTICATION_CLASSES': [
    # ...
    'rest_framework.authentication.SessionAuthentication',  # Opcional
    'rest_framework.authentication.BasicAuthentication',  # Opcional
    'mty_django_firebase_auth.authentication.FirebaseAuthentication',
  ]
}
```


La aplicación `mty_django_firebase_auth` viene con las siguientes configuraciones por defecto, las cuales pueden ser sobreescritas en el archivo `settings.py` de tu proyecto. Para mayor comodidad en la versión >= 1, la mayoría de estas configuraciones pueden ser establecidas desde variables de entorno. Asegurate de anidarlas dentro de `MTY_FIREBASE_AUTH` como se muestra a continuación:

```python    
import os
from mty_django_firebase_auth.utils import map_firebase_uid_to_username
# ...
# Los import de arriba es solo ilustrativo, no es necesario importarlo de nuevo pués el código ya lo tiene, es solo para que se entienda que se debe importar la librería os
# ...

MTY_FIREBASE_AUTH = {
    # Permitir solicitudes anónimas sin el encabezado de autorización
    'ALLOW_ANONYMOUS_REQUESTS': os.getenv('ALLOW_ANONYMOUS_REQUESTS', False),
    # Permitir la creación de un nuevo usuario local en la base de datos
    'FIREBASE_CREATE_LOCAL_USER': os.getenv('FIREBASE_CREATE_LOCAL_USER', True),
    # Intentar dividir el nombre de usuario de firebase y establecer el nombre y apellido del usuario local
    'FIREBASE_ATTEMPT_CREATE_WITH_DISPLAY_NAME': os.getenv('FIREBASE_ATTEMPT_CREATE_WITH_DISPLAY_NAME', True),
    # Prefijo del encabezado de autorización, usualmente JWT o Bearer (v.gr. Bearer <token>)
    'FIREBASE_AUTH_HEADER_PREFIX': os.getenv('FIREBASE_AUTH_HEADER_PREFIX', 'Bearer'),
    # Verificar que el JWT no haya sido revocado
    'FIREBASE_CHECK_JWT_REVOKED': os.getenv('FIREBASE_CHECK_JWT_REVOKED', True),
    # require that firebase user.email_verified is True
    # Requerir que el usuario de firebase tenga el correo verificado
    'FIREBASE_AUTH_EMAIL_VERIFICATION': os.getenv('FIREBASE_AUTH_EMAIL_VERIFICATION', False),
    # Función de mapeo de uid de firebase con username de django. 
    # La función debe aceptar firebase_admin.auth.UserRecord como argumento y devolver str
    'FIREBASE_USERNAME_MAPPING_FUNC': map_firebase_uid_to_username
}
```

Se pueden dejar todas las configuraciones por defecto.

NOTA: `FIREBASE_USERNAME_MAPPING_FUNC` reemplazará el comportamiento en la versión < 1 como predeterminado (anteriormente proporcionado por la lógica en `map_firebase_to_username_legacy`, descrito a continuación). Simplemente se puede cambiar esta función.

La configuración requiere cuentas de servicio de GCP, el proyecto original solo admite una; se ha modificado el código original para permitir más de una cuenta de servicio, Para configurar las cuentas de servicio, se debe agregar la siguiente configuración en el archivo `settings.py` de tu proyecto:

```python

MTY_FIREBASE_AUTH_PROJECTS = {
    # ...
    'FIREBASE_SERVICE_ACCOUNTS': {
        'A': A,
        'B': B,
        'C': C,
    }
}
```


`mty_django_firebase_auth.utils` contiene funciones para mapear la información del usuario de firebase al campo de nombre de usuario de Django (nuevo en la versión >= 1). Cualquier función personalizada puede ser suministrada aquí, siempre y cuando acepte un argumento `firebase_admin.auth.UserRecord`. Las funciones suministradas son casos de uso comunes:

```python
import uuid
from firebase_admin import auth
from mty_django_firebase_auth.utils import get_firebase_user_email
# ...
# Los import de arriba es solo ilustrativo, no es necesario importarlo de nuevo pués el código ya lo tiene, es solo para que se entienda que se debe importar las librerías
# ...

def map_firebase_to_username_legacy(firebase_user: auth.UserRecord) -> str:
    try:
        username = '_'.join(
            firebase_user.display_name.split(' ')
            if firebase_user.display_name
            else str(uuid.uuid4())
        )
        return username if len(username) <= 30 else username[:30]
    except Exception as e:
        raise Exception(e)


def map_firebase_display_name_to_username(firebase_user: auth.UserRecord) -> str:
    try:
        return '_'.join(firebase_user.display_name.split(' '))
    except Exception as e:
        raise Exception(e)


def map_firebase_uid_to_username(firebase_user: auth.UserRecord) -> str:
    try:
        return firebase_user.uid
    except Exception as e:
        raise Exception(e)


def map_firebase_email_to_username(firebase_user: auth.UserRecord) -> str:
    try:
        return get_firebase_user_email(firebase_user)
    except Exception as e:
        raise Exception(e)


def map_uuid_to_username(_: auth.UserRecord) -> str:
    try:
        return str(uuid.uuid4())
    except Exception as e:
        raise Exception(e)
```

Una vez que se ha configurado la aplicación, ejecutar las migraciones para que los datos de Firebase se puedan almacenar.

```
(venv) $ ./manage.py migrate mty_django_firebase_auth
```

Ahora solo necesitas que tu código cliente maneje el flujo de autenticación de Firebase popup/redirect, recuperar el idToken del currentUser (Firebase explica bien este flujo en su documentación: `https://firebase.google.com/docs/auth/admin/verify-id-tokens`), y luego usar el idToken para el usuario en un encabezado `Authorization` en las solicitudes a tu API.

```
Bearer <token>
```

Voila!

## Contributing

* Please raise an issue/feature and name your branch 'feature-n' or 'issue-n', where 'n' is the issue number.
