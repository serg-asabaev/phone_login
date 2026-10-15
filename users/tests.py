# users/tests.py
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import User, SMSCode
from .services import generate_invite_code


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': (
            'rest_framework_simplejwt.authentication.JWTAuthentication',
        ),
        'DEFAULT_THROTTLE_CLASSES': [],
        'DEFAULT_THROTTLE_RATES': {},
    },
    DEBUG=True,
)
class BaseAPITestCase(APITestCase):
    """Базовый класс для всех API тестов"""
    pass


# ============================================================
# ТЕСТЫ УТИЛИТ
# ============================================================

class TestUtils(TestCase):
    """Тесты вспомогательных функций"""

    def test_generate_invite_code_length(self):
        """Код должен быть ровно 6 символов"""
        code = generate_invite_code()
        self.assertEqual(len(code), 6)

    def test_generate_invite_code_characters(self):
        """Код должен содержать только разрешённые символы"""
        allowed_chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        for _ in range(100):
            code = generate_invite_code()
            for char in code:
                self.assertIn(char, allowed_chars)

    def test_generate_invite_code_no_similar_chars(self):
        """В коде не должно быть похожих символов: 0, O, 1, I, l"""
        forbidden = {'0', 'O', '1', 'I', 'l'}
        for _ in range(100):
            code = generate_invite_code()
            for char in code:
                self.assertNotIn(char, forbidden)

    def test_generate_invite_code_uniqueness(self):
        """При 1000 генерациях должны быть разные коды"""
        codes = {generate_invite_code() for _ in range(1000)}
        self.assertGreater(len(codes), 900)


# ============================================================
# ТЕСТЫ ЗАПРОСА SMS-КОДА
# ============================================================

class TestRequestCodeEndpoint(BaseAPITestCase):
    """Тесты эндпоинта POST /api/auth/phone/request-code/"""

    def setUp(self):
        self.url = reverse('users:phone-auth-request-code')
        self.phone = '+79991234567'

    def test_request_code_success(self):
        """Успешный запрос кода для нового номера"""
        response = self.client.post(self.url, {'phone': self.phone}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('debug_code', response.data)
        self.assertEqual(len(response.data['debug_code']), 4)

        # Проверяем, что код сохранён в БД
        sms_code = SMSCode.objects.filter(phone=self.phone, is_used=False).first()
        self.assertIsNotNone(sms_code)
        self.assertEqual(sms_code.code, response.data['debug_code'])

    def test_request_code_invalid_phone(self):
        """Запрос с невалидным номером телефона"""
        response = self.client.post(self.url, {'phone': 'invalid'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_request_code_empty_phone(self):
        """Запрос без номера телефона"""
        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_request_code_replaces_existing(self):
        """Новый запрос должен заменить предыдущий код"""
        # Первый запрос
        self.client.post(self.url, {'phone': self.phone}, format='json')
        first_code = SMSCode.objects.get(phone=self.phone, is_used=False).code

        # Второй запрос
        self.client.post(self.url, {'phone': self.phone}, format='json')

        # Старый код должен быть удалён
        active_codes = SMSCode.objects.filter(phone=self.phone, is_used=False)
        self.assertEqual(active_codes.count(), 1)
        self.assertNotEqual(active_codes.first().code, first_code)


# ============================================================
# ТЕСТЫ ПОДТВЕРЖДЕНИЯ КОДА
# ============================================================

class TestVerifyCodeEndpoint(BaseAPITestCase):
    """Тесты эндпоинта POST /api/auth/phone/verify-code/"""

    def setUp(self):
        self.url = reverse('users:phone-auth-verify-code')
        self.phone = '+79991234567'
        self.sms_code = SMSCode.generate_code(self.phone, expires_minutes=5)

    def test_verify_code_new_user_registration(self):
        """Успешная регистрация нового пользователя"""
        data = {
            'phone': self.phone,
            'code': self.sms_code.code
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_new_user'])
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        # Пользователь создан
        user = User.objects.get(phone=self.phone)
        self.assertEqual(user.phone, self.phone)
        self.assertIsNotNone(user.invite_code)
        self.assertEqual(len(user.invite_code), 6)

        # SMS-код помечен как использованный
        self.sms_code.refresh_from_db()
        self.assertTrue(self.sms_code.is_used)

    def test_verify_code_existing_user_login(self):
        """Успешный вход существующего пользователя"""
        user = User.objects.create_user(phone=self.phone)
        sms_code = SMSCode.generate_code(self.phone)

        data = {
            'phone': self.phone,
            'code': sms_code.code
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_new_user'])
        self.assertEqual(response.data['user']['id'], user.id)

    def test_verify_code_wrong_code(self):
        """Неверный код"""
        data = {
            'phone': self.phone,
            'code': '0000'
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data)

    def test_verify_code_expired_code(self):
        """Истёкший код"""
        self.sms_code.expires_at = timezone.now() - timedelta(minutes=1)
        self.sms_code.save()

        data = {
            'phone': self.phone,
            'code': self.sms_code.code
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_code_already_used(self):
        """Повторное использование кода"""
        self.client.post(self.url, {
            'phone': self.phone,
            'code': self.sms_code.code
        }, format='json')

        response = self.client.post(self.url, {
            'phone': self.phone,
            'code': self.sms_code.code
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_code_nonexistent_code(self):
        """Код для номера не запрашивался"""
        data = {
            'phone': '+79990000000',
            'code': '1234'
        }
        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================
# ТЕСТЫ ПРОФИЛЯ
# ============================================================

class TestProfileEndpoint(BaseAPITestCase):
    """Тесты эндпоинта GET /api/auth/phone/me/"""

    def setUp(self):
        self.url = reverse('users:phone-auth-me')
        self.user = User.objects.create_user(phone='+79991234567')
        self.client.force_authenticate(user=self.user)

    def test_get_profile_authenticated(self):
        """Получение профиля авторизованным пользователем"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone'], self.user.phone)
        self.assertEqual(response.data['id'], self.user.id)
        self.assertIn('invite_code', response.data)
        self.assertIn('has_used_invite', response.data)

    def test_get_profile_unauthenticated(self):
        """Попытка получить профиль без авторизации"""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_shows_invite_code(self):
        """Профиль должен содержать инвайт-код"""
        response = self.client.get(self.url)

        self.assertIsNotNone(response.data['invite_code'])
        self.assertEqual(len(response.data['invite_code']), 6)

    def test_profile_shows_inviter_info(self):
        """Профиль должен показывать информацию о пригласившем"""
        inviter = User.objects.create_user(phone='+79998888888')
        self.user.invited_by = inviter
        self.user.save()

        response = self.client.get(self.url)

        self.assertIsNotNone(response.data['invited_by'])
        self.assertEqual(response.data['invited_by']['phone'], inviter.phone)
        self.assertTrue(response.data['has_used_invite'])


# ============================================================
# ТЕСТЫ АКТИВАЦИИ ИНВАЙТ-КОДА
# ============================================================

class TestApplyInviteEndpoint(BaseAPITestCase):
    """Тесты эндпоинта POST /api/auth/phone/apply-invite/"""

    def setUp(self):
        self.url = reverse('users:phone-auth-apply-invite')
        self.user = User.objects.create_user(phone='+79991234567')
        self.inviter = User.objects.create_user(phone='+79998888888')
        self.client.force_authenticate(user=self.user)

    def test_apply_invite_success(self):
        """Успешная активация инвайт-кода"""
        response = self.client.post(self.url, {
            'invite_code': self.inviter.invite_code
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Инвайт-код успешно активирован', response.data['message'])

        self.user.refresh_from_db()
        self.assertEqual(self.user.invited_by, self.inviter)

    def test_apply_invite_case_insensitive(self):
        """Регистр кода не должен иметь значения"""
        response = self.client.post(self.url, {
            'invite_code': self.inviter.invite_code.lower()
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_apply_invite_nonexistent_code(self):
        """Несуществующий инвайт-код"""
        response = self.client.post(self.url, {
            'invite_code': 'ZZZZZZ'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_invite_own_code(self):
        """Нельзя использовать свой собственный код"""
        response = self.client.post(self.url, {
            'invite_code': self.user.invite_code
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_invite_already_used(self):
        """Повторная активация инвайт-кода запрещена"""
        self.client.post(self.url, {
            'invite_code': self.inviter.invite_code
        }, format='json')

        another_inviter = User.objects.create_user(phone='+79997777777')

        response = self.client.post(self.url, {
            'invite_code': another_inviter.invite_code
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_apply_invite_unauthenticated(self):
        """Неавторизованный пользователь не может активировать код"""
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url, {
            'invite_code': self.inviter.invite_code
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# ТЕСТЫ СПИСКА ПРИГЛАШЁННЫХ
# ============================================================

class TestMyInvitedUsersEndpoint(BaseAPITestCase):
    """Тесты эндпоинта GET /api/auth/phone/my-invited-users/"""

    def setUp(self):
        self.url = reverse('users:phone-auth-my-invited-users')
        self.inviter = User.objects.create_user(phone='+79991234567')
        self.client.force_authenticate(user=self.inviter)

    def test_get_invited_users_empty(self):
        """Список приглашённых пуст, если никого не приглашали"""
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['users'], [])

    def test_get_invited_users_with_data(self):
        """Список приглашённых с данными"""
        user1 = User.objects.create_user(phone='+79992222222')
        user2 = User.objects.create_user(phone='+79993333333')
        user1.invited_by = self.inviter
        user1.save()
        user2.invited_by = self.inviter
        user2.save()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

        phones = [u['phone'] for u in response.data['users']]
        self.assertIn('+79992222222', phones)
        self.assertIn('+79993333333', phones)

    def test_get_invited_users_excludes_others(self):
        """В списке должны быть только приглашённые текущим пользователем"""
        other_inviter = User.objects.create_user(phone='+79999999999')

        user = User.objects.create_user(phone='+79994444444')
        user.invited_by = other_inviter
        user.save()

        response = self.client.get(self.url)

        self.assertEqual(response.data['count'], 0)

    def test_get_invited_users_unauthenticated(self):
        """Неавторизованный доступ запрещён"""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# ============================================================

class TestFullRegistrationFlow(BaseAPITestCase):
    """Полный сценарий: регистрация + реферальная система"""

    def test_full_flow_two_users_with_referral(self):
        """
        Сценарий:
        1. Пользователь A регистрируется
        2. Пользователь B регистрируется
        3. Пользователь B активирует инвайт-код пользователя A
        4. Пользователь A видит B в списке приглашённых
        """
        # === Шаг 1: Регистрация пользователя A ===
        phone_a = '+79991111111'

        response = self.client.post(
            reverse('users:phone-auth-request-code'),
            {'phone': phone_a},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        code_a = response.data['debug_code']

        response = self.client.post(
            reverse('users:phone-auth-verify-code'),
            {'phone': phone_a, 'code': code_a},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token_a = response.data['access']
        invite_code_a = response.data['user']['invite_code']

        # === Шаг 2: Регистрация пользователя B ===
        phone_b = '+79992222222'

        response = self.client.post(
            reverse('users:phone-auth-request-code'),
            {'phone': phone_b},
            format='json'
        )
        code_b = response.data['debug_code']

        response = self.client.post(
            reverse('users:phone-auth-verify-code'),
            {'phone': phone_b, 'code': code_b},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token_b = response.data['access']

        # === Шаг 3: Пользователь B активирует инвайт-код A ===
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_b}')

        response = self.client.post(
            reverse('users:phone-auth-apply-invite'),
            {'invite_code': invite_code_a},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['has_used_invite'])

        # === Шаг 4: Пользователь A видит B в списке ===
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_a}')

        response = self.client.get(reverse('users:phone-auth-my-invited-users'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['users'][0]['phone'], phone_b)

        # === Шаг 5: Проверка профиля пользователя B ===
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_b}')

        response = self.client.get(reverse('users:phone-auth-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['has_used_invite'])
        self.assertEqual(response.data['invited_by']['phone'], phone_a)

    def test_cannot_use_invite_twice(self):
        """Пользователь не может использовать инвайт-код дважды"""
        inviter = User.objects.create_user(phone='+79991111111')

        phone = '+79992222222'
        response = self.client.post(
            reverse('users:phone-auth-request-code'),
            {'phone': phone},
            format='json'
        )
        code = response.data['debug_code']

        response = self.client.post(
            reverse('users:phone-auth-verify-code'),
            {'phone': phone, 'code': code},
            format='json'
        )
        token = response.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Первая активация — успех
        response = self.client.post(
            reverse('users:phone-auth-apply-invite'),
            {'invite_code': inviter.invite_code},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Вторая активация — ошибка
        another_inviter = User.objects.create_user(phone='+79993333333')
        response = self.client.post(
            reverse('users:phone-auth-apply-invite'),
            {'invite_code': another_inviter.invite_code},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)