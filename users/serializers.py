from rest_framework import serializers

from .models import User,SMSCode
import re
from .services import generate_invite_code

def validate_phone_format(value):
    """Валидация формата телефона"""
    # Простая валидация - только цифры и знак + в начале
    if not re.match(r'^\+?[0-9]{10,15}$', value):
        raise serializers.ValidationError("Неверный формат номера телефона")
    return value

class RequestCodeSerializer(serializers.Serializer):
    phone = serializers.CharField(validators=[validate_phone_format])

    def validate_phone(self, value):
        return value


class VerifyCodeSerializer(serializers.Serializer):
    phone = serializers.CharField(validators=[validate_phone_format])
    code = serializers.CharField(max_length=4)

    def validate(self, attrs):
        phone = attrs.get('phone')
        code = attrs.get('code')

        # Ищем последний неиспользованный код для этого телефона
        sms_code = SMSCode.objects.filter(
            phone=phone,
            is_used=False
        ).order_by('-created_at').first()

        if not sms_code:
            raise serializers.ValidationError({
                'code': 'Код не найден или уже использован'
            })

        if not sms_code.is_valid():
            raise serializers.ValidationError({
                'code': 'Код истек'
            })

        if sms_code.code != code:
            raise serializers.ValidationError({
                'code': 'Неверный код'
            })

        # Помечаем код как использованный
        sms_code.mark_as_used()

        attrs['phone'] = phone
        attrs['invite_code'] = generate_invite_code()
        return attrs

class InviterSerializer(serializers.ModelSerializer):
    """Сериализатор для информации о пригласившем пользователе"""
    class Meta:
        model = User
        fields = ('id', 'phone')
        read_only_fields = ('id', 'phone')

# users/serializers.py
class UserSerializer(serializers.ModelSerializer):
    invited_by = InviterSerializer(read_only=True)
    has_used_invite = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'phone',
            'invite_code',  # Собственный код пользователя
            'invited_by',  # Информация о пригласившем
            'has_used_invite',  # Флаг использования инвайт-кода
            'is_active',
            'date_joined'
        )
        read_only_fields = ('id', 'date_joined', 'invite_code')

    def get_has_used_invite(self, obj):
        """Возвращает True, если пользователь уже активировал инвайт-код"""
        return obj.invited_by is not None

class InviteRegistrationSerializer(serializers.Serializer):
    phone = serializers.CharField()
    invite_code = serializers.CharField(max_length=6)

    def validate_invite_code(self, value):
        # Приводим к верхнему регистру и убираем пробелы
        value = value.upper().strip()

        # Получаем текущего пользователя из контекста
        user = self.context['request'].user

        # 1. Проверяем, что пользователь еще не использовал инвайт-код
        if user.invited_by is not None:
            raise serializers.ValidationError(
                "Вы уже активировали инвайт-код. Повторная активация невозможна."
            )

        # 2. Проверяем, что код существует
        try:
            inviter = User.objects.get(invite_code=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Инвайт-код не найден")

        # 3. Проверяем, что пользователь не пытается пригласить сам себя
        if inviter == user:
            raise serializers.ValidationError("Нельзя использовать свой собственный инвайт-код")

        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        invite_code = self.validated_data['invite_code']

        # Находим пригласившего
        inviter = User.objects.get(invite_code=invite_code)

        # Устанавливаем связь
        user.invited_by = inviter
        user.save()

        return user
    def create(self, validated_data):
        # Создаем пользователя. Менеджер автоматически сгенерирует ему свой собственный invite_code
        user = User.objects.create_user(
            phone=validated_data['phone']
        )
        return user


class ApplyInviteCodeSerializer(serializers.Serializer):
    invite_code = serializers.CharField(max_length=6)

    def validate_invite_code(self, value):
        # Приводим к верхнему регистру
        value = value.upper().strip()

        # Получаем текущего пользователя из контекста
        user = self.context['request'].user

        # 1. Проверяем, что код существует
        try:
            inviter = User.objects.get(invite_code=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Инвайт-код не найден")

        # 2. Проверяем, что пользователь не пытается пригласить сам себя
        if inviter == user:
            raise serializers.ValidationError("Нельзя использовать свой собственный инвайт-код")

        # 3. Проверяем, что пользователь еще не был приглашен (опционально)
        if user.invited_by is not None:
            raise serializers.ValidationError("Вы уже использовали инвайт-код")

        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        invite_code = self.validated_data['invite_code']

        # Находим пригласившего
        inviter = User.objects.get(invite_code=invite_code)

        # Устанавливаем связь
        user.invited_by = inviter
        user.save()

        return user
