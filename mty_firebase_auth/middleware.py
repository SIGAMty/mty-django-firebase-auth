from django.utils.deprecation import MiddlewareMixin
from django.db import IntegrityError
import requests.exceptions
from django.contrib.auth import get_user_model
from django.contrib import auth
from django.utils import timezone
from .settings import api_settings
import logging
from mty_firebase_auth import __title__
from firebase_admin import auth as firebase_admin_auth
from typing import Tuple, Dict
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import SimpleLazyObject
from .models import FirebaseUser, FirebaseUserProvider
from .utils import get_firebase_user_email
import firebase
import json
import os

log = logging.getLogger(__title__)
User = get_user_model()

with open(api_settings.FIREBASE_APP_CONFIG_KEY) as config_file:
    firebase_app = firebase.initialize_app(json.load(config_file))
    firebase_auth = firebase_app.auth()


class FirebaseEmailPasswordAuthMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

    def __call__(self, request):
        self.firebase_email_login(request)

        response = self.get_response(request)
        print("CALL TERMINADO", response)
        return response

    def _authenticate_token(self, decoded_token: Dict) -> firebase_admin_auth.UserRecord:
        """ Returns firebase user if token is authenticated """
        try:
            uid = decoded_token.get('uid')
            log.info(f'_authenticate_token - uid: {uid}')
            firebase_user = firebase_admin_auth.get_user(uid)
            log.info(f'_authenticate_token - firebase_user: {firebase_user}')
            if api_settings.FIREBASE_AUTH_EMAIL_VERIFICATION:
                if not firebase_user.email_verified:
                    raise Exception('Email address of this user has not been verified.')
            return firebase_user
        except Exception as e:
            log.error(f'_authenticate_token - Exception: {e}')
            raise Exception(e)

    def _authenticate_useremail(self, email, password):
        try:
            log.info(f'_authenticate_user: {email}')
            login_user = firebase_auth.sign_in_with_email_and_password(email, password)
            decoded_token = firebase_admin_auth.verify_id_token(login_user['idToken'],
                                                                check_revoked=api_settings.FIREBASE_CHECK_JWT_REVOKED)
            uid = decoded_token.get('uid')
            firebase_user = firebase_admin_auth.get_user(uid)
            return firebase_user
        except Exception:
            pass
            # log.error(f'_authenticate_token - Exception: {e}')
            # raise Exception(e)

    def _get_or_create_local_user(self, firebase_user: firebase_admin_auth.UserRecord) -> User:
        """
        Attempts to return or create a local User from Firebase user data
        """
        email = get_firebase_user_email(firebase_user)
        log.info(f'_get_or_create_local_user - email: {email}')
        user = None
        try:
            user = User.objects.get(email__iexact=email)
            print("user exists", user)
            log.info(
                f'_get_or_create_local_user - user.is_active: {user.is_active}'
            )
            if not user.is_active:
                print("user exists but is not active", user)
                raise Exception(
                    'User account is not currently active.'
                )
            user.last_login = timezone.now()
            user.save()
            print("user exists and last login saved", user)
        except User.DoesNotExist as e:
            print("User does not exist", e)
            log.error(
                f'_get_or_create_local_user - User.DoesNotExist: {email}'
            )
            if not api_settings.FIREBASE_CREATE_LOCAL_USER:
                raise Exception('User is not registered to the application.')
            username = api_settings.FIREBASE_USERNAME_MAPPING_FUNC(firebase_user)
            log.info(
                f'_get_or_create_local_user - username: {username}'
            )
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email
                )
                user.last_login = timezone.now()
                if (
                        api_settings.FIREBASE_ATTEMPT_CREATE_WITH_DISPLAY_NAME
                        and firebase_user.display_name is not None
                ):
                    display_name = firebase_user.display_name.split(' ')
                    if len(display_name) == 2:
                        user.first_name = display_name[0]
                        user.last_name = display_name[1]
                user.save()
            except Exception as e:
                raise Exception(e)
        return user

    def _create_local_firebase_user(self, user: User, firebase_user: firebase_admin_auth.UserRecord):
        """ Create a local FireBase model if one does not already exist """
        # pylint: disable=no-member
        local_firebase_user = FirebaseUser.objects.filter(
            user=user
        ).first()

        print("JA")
        print("local_firebase_user", local_firebase_user)

        if not local_firebase_user:
            print("no existe local_firebase_user")
            new_firebase_user = FirebaseUser(
                uid=firebase_user.uid,
                user=user
            )
            new_firebase_user.save()
            local_firebase_user = new_firebase_user

        if local_firebase_user.uid != firebase_user.uid:
            local_firebase_user.uid = firebase_user.uid
            local_firebase_user.save()

        # store FirebaseUserProvider data
        for provider in firebase_user.provider_data:
            local_provider = FirebaseUserProvider.objects.filter(
                provider_id=provider.provider_id,
                firebase_user=local_firebase_user
            ).first()
            if not local_provider:
                new_local_provider = FirebaseUserProvider.objects.create(
                    provider_id=provider.provider_id,
                    uid=provider.uid,
                    firebase_user=local_firebase_user,
                )
                new_local_provider.save()

        # catch locally stored providers no longer associated at Firebase
        local_providers = FirebaseUserProvider.objects.filter(
            firebase_user=local_firebase_user
        )
        if len(local_providers) != len(firebase_user.provider_data):
            current_providers = \
                [x.provider_id for x in firebase_user.provider_data]
            for provider in local_providers:
                if provider.provider_id not in current_providers:
                    FirebaseUserProvider.objects.filter(
                        id=provider.id
                    ).delete()

        print("terminado")

    def firebase_email_login(self, request, email=None, password=None):







        if request.method == 'POST' and 'login' in request.path:
            email = request.POST["username"]
            password = request.POST["password"]

            if email and password:
                firebase_user_login = self._authenticate_useremail(email, password)
                print("firebase_user", firebase_user_login)
                if firebase_user_login:
                    local_user = self._get_or_create_local_user(firebase_user_login)
                    self._create_local_firebase_user(local_user, firebase_user_login)
                    print("local_user", local_user)
                    # aqui debe aceptar el login y pasar..... maldita sea
                    return email, password

