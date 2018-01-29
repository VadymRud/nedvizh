from django.contrib.auth.backends import ModelBackend
from django.core.validators import validate_email
from custom_user.models import User

class EmailBackend(ModelBackend):
    def authenticate(self, username=None, password=None):
        authenticated_user = None
        username = username.strip()
        if '@' not in username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                pass
            else:
                if user.check_password(password):
                    authenticated_user = user
        elif validate_email(username) is None:
            for user in User.objects.filter(email__iexact=username).order_by('-social_auth'):
                if user.check_password(password):
                    authenticated_user = user
                    break
        return authenticated_user
