from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
import random
import string

from .services import generate_invite_code

class CustomUserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('Номер телефона обязателен')

        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.invite_code = self._generate_unique_invite_code()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Суперпользователь должен иметь is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Суперпользователь должен иметь is_superuser=True.')

        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=18, unique=True, verbose_name='Телефон')

    invite_code = models.CharField(
        max_length=6,
        unique=True,
        blank=True,
        verbose_name='Инвайт-код'
    )

    invited_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invited_users',
        verbose_name='Пригласил'
    )

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    # КЛЮЧЕВОЙ МОМЕНТ: указываем поле для аутентификации
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone

    def save(self, *args, **kwargs):
        # Генерируем инвайт-код при создании, если он не задан
        if not self.invite_code:
            self.invite_code = self._generate_unique_invite_code()
        super().save(*args, **kwargs)

    def _generate_unique_invite_code(self):
        """Генерирует уникальный инвайт-код"""
        while True:
            code = generate_invite_code()
            if not User.objects.filter(invite_code=code).exists():
                return code

    @property
    def invited_count(self):
        return self.invited_users.count()


class SMSCode(models.Model):
    """Модель для хранения SMS-кодов подтверждения"""
    phone = models.CharField(max_length=18, verbose_name='Телефон')
    code = models.CharField(max_length=4, verbose_name='Код')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    expires_at = models.DateTimeField(verbose_name='Истекает')
    is_used = models.BooleanField(default=False, verbose_name='Использован')

    class Meta:
        verbose_name = 'SMS код'
        verbose_name_plural = 'SMS коды'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone}: {self.code}'

    @classmethod
    def generate_code(cls, phone, expires_minutes=5):
        """Генерирует новый код для телефона"""
        # Удаляем все неиспользованные коды для этого телефона
        cls.objects.filter(phone=phone, is_used=False).delete()

        # Генерируем 6-значный код
        code = ''.join(random.choices(string.digits, k=4))

        # Создаем новый код
        expires_at = timezone.now() + timezone.timedelta(minutes=expires_minutes)
        sms_code = cls.objects.create(
            phone=phone,
            code=code,
            expires_at=expires_at
        )

        return sms_code

    def is_valid(self):
        """Проверяет, действителен ли код"""
        return not self.is_used and timezone.now() < self.expires_at

    def mark_as_used(self):
        """Помечает код как использованный"""
        self.is_used = True
        self.save()