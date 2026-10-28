from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.accounts.models import User, Organization

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = user.role
        token['org_id'] = user.org_id
        token['org_name'] = user.org.name
        token['property_ids'] = user.property_ids
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data['user'] = {
            'id': user.id,
            'email': user.email,
            'role': user.role,
            'org_id': user.org_id,
            'org_name': user.org.name,
            'property_ids': user.property_ids,
        }
        return data


class UserSerializer(serializers.ModelSerializer):
    property_ids = serializers.ReadOnlyField()
    org_name = serializers.ReadOnlyField(source='org.name')

    class Meta:
        model = User
        fields = ('id', 'email', 'role', 'org_id', 'org_name', 'property_ids', 'is_active', 'created_at')
        read_only_fields = fields


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ('id', 'name', 'slug', 'created_at')
        read_only_fields = fields
