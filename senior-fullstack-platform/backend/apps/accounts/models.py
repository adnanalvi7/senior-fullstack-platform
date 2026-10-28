from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

class Organization(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'org_admin')

        if not extra_fields.get('org_id') and not extra_fields.get('org'):
            org, _ = Organization.objects.get_or_create(
                slug='admin-org',
                defaults={'name': 'System Administration Org'}
            )
            extra_fields['org'] = org

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('org_admin', 'Organization Admin'),
        ('property_manager', 'Property Manager'),
        ('approver', 'Approver'),
        ('viewer', 'Viewer'),
    )

    email = models.EmailField(unique=True, db_index=True)
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='users', db_index=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default='viewer', db_index=True)
    assigned_properties = models.ManyToManyField(
        'properties.Property',
        through='UserPropertyAccess',
        related_name='assigned_users',
        blank=True
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.email} ({self.role} - Org {self.org_id})"

    @property
    def property_ids(self):
        if self.role == 'org_admin':
            return list(self.org.properties.values_list('id', flat=True))
        return list(self.assigned_properties.values_list('id', flat=True))


class UserPropertyAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='property_accesses')
    property = models.ForeignKey('properties.Property', on_delete=models.CASCADE, related_name='user_accesses')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'property')
        indexes = [
            models.Index(fields=['user', 'property']),
        ]

    def __str__(self):
        return f"User {self.user_id} -> Property {self.property_id}"
