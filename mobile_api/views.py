# coding=utf-8
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from registration.signals import user_registered
from rest_framework.status import HTTP_401_UNAUTHORIZED, HTTP_204_NO_CONTENT, HTTP_403_FORBIDDEN
from rest_framework.views import APIView

from _site.urls import MestoRegistrationView
from mobile_api.serializers import UserSerializer
from custom_user.models import User

from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator

from django import forms
from django.utils.translation import ugettext_lazy as _

from profile.models import Message


class MessageREST(APIView):
    queryset = Message.objects.none()

    def delete(self, request, message_id, format=None):
        if request.user.is_anonymous():
            return Response(status=HTTP_401_UNAUTHORIZED)

        root_message = Message.objects.filter(
            Q(id=message_id) & (Q(from_user=request.user) | Q(to_user=request.user))
        ).first()

        if root_message is None:
            return Response(status=HTTP_403_FORBIDDEN)

        root_message.hidden_for_user.add(request.user)

        return Response(status=HTTP_204_NO_CONTENT)


class PersonRegForm(forms.ModelForm):
    username = forms.CharField(widget=forms.HiddenInput, required=False)
    email = forms.EmailField(max_length=75, label=_("Email"))
    password1 = forms.CharField(widget=forms.PasswordInput(render_value=False), label=_("Password"))

    class Meta:
        model = User
        fields = ('email', 'password1')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).count():
            raise forms.ValidationError(_(u'Пользователь с таким email-адресом уже зарегистрирован'))
        return email

    def clean(self):
        super(PersonRegForm, self).clean()
        if not self.errors:
            self.cleaned_data['username'] = '%s%s' % (self.cleaned_data['email'].split('@',1)[0], User.objects.count())
        if 'password1' in self.cleaned_data:
            self.cleaned_data['password2'] = self.cleaned_data['password1']
        return self.cleaned_data

@api_view(['POST'])
@permission_classes((AllowAny,))
def create_auth(request):
    serialized = UserSerializer(data=request.data, context={'request': request})
    init_data = serialized.initial_data.copy()
    init_data['password1'] = init_data['password2'] = init_data.get('password')

    form = PersonRegForm(init_data, instance=User())
    if serialized.is_valid() and form.is_valid():
        new_user = get_user_model().objects.create_user(
            email=init_data['email'],
            username=init_data['username'],
            password=init_data['password'],
            first_name=init_data['first_name'],
            last_name=init_data['last_name'],
        )
        user_registered.send(sender=MestoRegistrationView, user=new_user, request=request)

        return Response(UserSerializer(new_user, context={'request': request}).data, status=status.HTTP_201_CREATED)
    else:
        errors = dict(form.errors.items() + serialized._errors.items())
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes((AllowAny,))
def restore_password(request):
    serialized = UserSerializer(data=request.data, context={'request': request})
    request.POST = serialized.initial_data.copy()

    form = PasswordResetForm(request.POST)
    if form.is_valid():
        opts = {
            'use_https': request.is_secure(),
            'token_generator': default_token_generator,
            'from_email': None,
            'email_template_name': 'registration/password_reset_email.html',
            'subject_template_name': 'registration/password_reset_subject.txt',
            'request': request,
        }
        form.save(**opts)

        return Response({'Password reset successful'}, status=status.HTTP_200_OK)
    else:
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
