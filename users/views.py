import jwt
from datetime import datetime, timedelta
import random
import string

from django.contrib.auth import authenticate
from django.conf import settings

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from users.models import User, Jwt
from users.authentications import Authentication
from users.serializers import LoginSerializer, RegisterSerializer, RefreshSerializer


def get_random(length):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def get_access_token(payload):
    return jwt.encode(
        {"exp": datetime.now() + timedelta(minutes=5), **payload},
        settings.SECRET_KEY,
        algorithm="HS256"
    )


def get_refresh_token():
    return jwt.encode(
        {"exp": datetime.now() + timedelta(days=365), "data": get_random(10)},
        settings.SECRET_KEY,
        algorithm="HS256"
    )


class LoginView(APIView):
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'])

        if not user:
            return Response({"error": "Invalid username or password"}, status="400")

        Jwt.objects.filter(user_id=user.username).delete()

        access = get_access_token({"user_id": user.username})
        refresh = get_refresh_token()

        Jwt.objects.create(
            user_id=user.username, access=access, refresh=refresh
        )

        return Response({"access": access, "refresh": refresh})


class RegisterView(APIView):
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        User.objects._create_user(**serializer.validated_data)

        return Response({"success": "User created."})


class RefreshView(APIView):
    serializer_class = RefreshSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            active_jwt = Jwt.objects.get(
                refresh=serializer.validated_data["refresh"])
        except Jwt.DoesNotExist:
            return Response({"error": "refresh token not found"}, status="400")
        if not Authentication.verify_token(serializer.validated_data["refresh"]):
            return Response({"error": "Token is invalid or has expired"})

        access = get_access_token({"user_id": active_jwt.user.username})
        refresh = get_refresh_token()

        active_jwt.access = access.decode()
        active_jwt.refresh = refresh.decode()
        active_jwt.save()

        return Response({"access": access, "refresh": refresh})
