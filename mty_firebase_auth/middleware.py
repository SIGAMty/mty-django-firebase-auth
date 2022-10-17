from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth import get_user_model
from django.utils import timezone
from .settings import api_settings
import logging
from mty_firebase_auth import __title__
from firebase_admin import auth as firebase_admin_auth
from .models import FirebaseUser, FirebaseUserProvider
from .utils import get_firebase_user_email
from django.utils.functional import SimpleLazyObject
import firebase
import json
from django.contrib import auth
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.shortcuts import redirect
from django.http import HttpResponseRedirect, Http404

log = logging.getLogger(__title__)
User = get_user_model()

with open(api_settings.FIREBASE_APP_CONFIG_KEY) as config_file:
    firebase_app = firebase.initialize_app(json.load(config_file))
    firebase_auth = firebase_app.auth()


def get_user(request):
    if not hasattr(request, "_cached_user"):
        request._cached_user = auth.get_user(request)
    return request._cached_user


def authenticate_useremail(user_email, user_password):
    try:
        log.info(f'_authenticate_user: {user_email}')
        login_user = firebase_auth.sign_in_with_email_and_password(user_email, user_password)
        decoded_token = firebase_admin_auth.verify_id_token(login_user['idToken'],
                                                            check_revoked=api_settings.FIREBASE_CHECK_JWT_REVOKED)
        uid = decoded_token.get('uid')
        firebase_user = firebase_admin_auth.get_user(uid)
        return firebase_user
    except Exception:
        pass
        # log.error(f'_authenticate_token - Exception: {e}')
        # raise Exception(e)


def get_or_create_local_user(firebase_user: firebase_admin_auth.UserRecord) -> User:
    """
    Attempts to return or create a local User from Firebase user data
    """
    local_email = get_firebase_user_email(firebase_user)
    local_user = None
    log.info(f'_get_or_create_local_user - email: {local_email}')
    log.info(f'_get_or_create_local_user - user: {local_user}')

    try:
        local_user = User.objects.get(email__iexact=local_email)
        log.info(
            f'_get_or_create_local_user - user.is_active: {local_user.is_active}'
        )
        if not local_user.is_active:
            raise Exception(
                'User account is not currently active.'
            )
        local_user.last_login = timezone.now()
        local_user.save()
    except User.DoesNotExist as e:
        log.error(
            f'_get_or_create_local_user - User.DoesNotExist: {local_email}'
        )
        if not api_settings.FIREBASE_CREATE_LOCAL_USER:
            raise Exception('User is not registered to the application.')
        username = api_settings.FIREBASE_USERNAME_MAPPING_FUNC(firebase_user)
        log.info(
            f'_get_or_create_local_user - username: {username}'
        )
        try:
            local_user = User.objects.create_user(
                username=username,
                email=local_email
            )
            local_user.last_login = timezone.now()
            if (
                    api_settings.FIREBASE_ATTEMPT_CREATE_WITH_DISPLAY_NAME
                    and firebase_user.display_name
            ):
                display_name = firebase_user.display_name.split(' ')
                if len(display_name) == 2:
                    local_user.first_name = display_name[0]
                    local_user.last_name = display_name[1]
            local_user.save()
        except Exception as e:
            raise Exception(e)
    return local_user


def create_local_firebase_user(user: User, firebase_user: firebase_admin_auth.UserRecord):
    """ Create a local FireBase model if one does not already exist """
    # pylint: disable=no-member
    local_firebase_user = FirebaseUser.objects.filter(
        user=user
    ).first()

    if not local_firebase_user:
        print('Creating local FirebaseUser')
        new_firebase_user = FirebaseUser(
            uid=firebase_user.uid,
            user=user
        )
        new_firebase_user.save()
        local_firebase_user = new_firebase_user
    else:
        print('FirebaseUser User exists')

    if local_firebase_user.uid != firebase_user.uid:
        print('Updating local FirebaseUser')
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


class FirebaseEmailPasswordAuthMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response

    def __call__(self, request):
        login_response = self.firebase_email_login(request)
        response = self.get_response(request)
        return login_response or response

    def firebase_email_login(self, request, email=None, password=None):
        if not hasattr(request, "session"):
            raise ImproperlyConfigured(
                "The Django authentication middleware requires session "
                "middleware to be installed. Edit your MIDDLEWARE setting to "
                "insert "
                "'django.contrib.sessions.middleware.SessionMiddleware' before "
                "'django.contrib.auth.middleware.AuthenticationMiddleware'."
            )
        request.user = SimpleLazyObject(lambda: get_user(request))

        next = None
        if request.GET:
            next = request.GET.get('next', None)
            urlpath = request.path.split('login')[0]

            if next and urlpath == '/dadmin/' and request.user.is_authenticated and request.user.is_staff:
                return redirect(next)

            if next and urlpath == '/wadmin/' and request.user.is_authenticated and request.user.has_perm('wagtailadmin.access_admin'):
                return redirect(next)

        if request.POST and 'login' in request.path and request.user.is_authenticated is False:
            if request.POST["username"] and request.POST["password"]:

                email = request.POST["username"]
                password = request.POST["password"]

                if email and password:
                    firebase_user_login = authenticate_useremail(email, password)
                    if firebase_user_login:
                        get_local_user = get_or_create_local_user(firebase_user_login)
                        create_local_firebase_user(get_local_user, firebase_user_login)
                        login(request, get_local_user)


