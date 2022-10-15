from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import User
from django.db import IntegrityError
from .settings import api_settings
import requests.exceptions
import pyrebase
import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(PROJECT_DIR)

firebase = pyrebase.initialize_app(api_settings.FIREBASE_SERVICE_ACCOUNT_KEY)
firebase_auth = firebase.auth()


class FirebaseLoginEmail(MiddlewareMixin):
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

    def __call__(self, request):
        self.auth(request)
        return self.get_response(request)

    @staticmethod
    def auth(request, email=None, password=None):
        if 'login' in request.path:
            if request.method == 'POST':
                email = request.POST["username"]
                password = request.POST["password"]
            if email:
                try:
                    firebase_auth.sign_in_with_email_and_password(email, password)
                    try:
                        """
                        Se creo una cuenta en django siempre y cuando exista en firebase.
                        """
                        user = User.objects.create_user(username=email, email=email, password=password)
                        user.is_staff = True
                        user.save()
                    except IntegrityError as err:
                        """
                        Existe en ambos
                        UNIQUE constraint failed: auth_user.username
                        """
                        response = err.args[0]
                        if response == 'UNIQUE constraint failed: auth_user.username':
                            user = User.objects.get(username__exact=email)
                            user.set_password(password)
                            user.save()
                        return
                except requests.exceptions.HTTPError:
                    # response = e.args[0].response
                    # error = response.json()['error']
                    """
                    No esta dentro de firebase o contraseña incorrecta
                    """
                    return False
                return
