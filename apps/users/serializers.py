from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password
from .models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name',
                  'role', 'phone', 'avatar', 'is_active', 'date_joined', 'must_change_password']
        read_only_fields = ['id', 'date_joined', 'must_change_password']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'phone', 'password', 'password_confirm']

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid credentials.')
        if not user.is_active:
            raise serializers.ValidationError('Account is disabled.')
        data['user'] = user
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)


class SetupAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """Refuse refreshes until setup is complete and revoke tokens after a password change."""
    def validate(self, attrs):
        refresh = self.token_class(attrs['refresh'])
        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        if user_id:
            user_model = get_user_model()
            try:
                user = user_model.objects.get(**{api_settings.USER_ID_FIELD: user_id})
            except user_model.DoesNotExist:
                user = None
            if user is not None:
                if user.must_change_password:
                    from rest_framework.exceptions import AuthenticationFailed
                    raise AuthenticationFailed('Set a new password before refreshing this session.')
                if api_settings.CHECK_REVOKE_TOKEN and refresh.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
                    from rest_framework.exceptions import AuthenticationFailed
                    raise AuthenticationFailed('The password for this session has changed. Sign in again.')
        return super().validate(attrs)
