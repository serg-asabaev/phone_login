from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from drf_spectacular.types import OpenApiTypes



from .models import User, SMSCode
from .serializers import RequestCodeSerializer, VerifyCodeSerializer, UserSerializer, ApplyInviteCodeSerializer, InviterSerializer
from .forms import PhoneForm, SMSCodeForm, InviteCodeForm


class PhoneAuthViewSet(viewsets.GenericViewSet):
    """
    ViewSet для регистрации и авторизации по SMS-коду.
    """

    @extend_schema(
        summary="Запрос SMS-кода",
        description="Генерирует 6-значный код и отправляет его на указанный номер телефона.",
        request=RequestCodeSerializer,
        responses={200: OpenApiTypes.OBJECT}, # Можно указать конкретный serializer ответа
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny], serializer_class=RequestCodeSerializer, url_path='request-code')
    def request_code(self, request):
        """
        Запрос SMS-кода для регистрации или входа.

        Request:
        {
            "phone": "+79991234567"
        }

        Response:
        {
            "message": "Код отправлен",
            "debug_code": "123456"  # Только в DEBUG режиме
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']

        # Генерируем код (действителен 5 минут)
        sms_code = SMSCode.generate_code(phone, expires_minutes=5)

        response_data = {
            'message': 'Код отправлен на номер телефона'
        }

        # В DEBUG режиме возвращаем код для удобства тестирования
        if settings.DEBUG:
            response_data['debug_code'] = sms_code.code
            response_data['expires_in'] = 300  # 5 минут в секундах

        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Подтверждение кода и вход",
        description="Проверяет код. Если пользователь новый — создает его. Возвращает JWT токены.",
        request=VerifyCodeSerializer,
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny], serializer_class=VerifyCodeSerializer, url_path='verify-code')
    def verify_code(self, request):
        """
        Подтверждение кода и вход/регистрация.

        Если пользователь не существует - создается новый.
        Если существует - выполняется вход.

        Request:
        {
            "phone": "+79991234567",
            "code": "123456"
        }

        Response:
        {
            "message": "Успешный вход",
            "access": "jwt_access_token",
            "refresh": "jwt_refresh_token",
            "user": {...},
            "is_new_user": true/false
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']

        # Получаем или создаем пользователя
        user, created = User.objects.get_or_create(phone=phone)

        # Генерируем JWT токены
        refresh = RefreshToken.for_user(user)

        response_data = {
            'message': 'Успешный вход' if not created else 'Регистрация успешна',
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
            'is_new_user': created
        }

        return Response(response_data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAuthenticated],
        serializer_class=ApplyInviteCodeSerializer,
        url_path='apply-invite'
    )
    def apply_invite(self, request):
        """
        Ввести инвайт-код другого пользователя.
        Можно активировать только один раз.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response({
            'message': 'Инвайт-код успешно активирован',
            'invited_by': InviterSerializer(user.invited_by).data,
            'has_used_invite': True
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated], url_path='my-invited-users')
    def my_invited_users(self, request):
        """Получить список пользователей, которых пригласил текущий пользователь"""
        invited = User.objects.filter(invited_by=request.user)
        serializer = UserSerializer(invited, many=True)
        return Response({
            'count': invited.count(),
            'users': serializer.data
        })

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated],
        serializer_class=UserSerializer,
        url_path='me'  # ← ДОЛЖНО БЫТЬ ИМЕННО 'me'
    )
    def me(self, request):
        """Получить информацию о текущем пользователе"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PhoneInputView(View):
    """
    Шаг 1: Ввод номера телефона.
    Генерирует SMS-код и сохраняет телефон в сессии.
    """
    template_name = 'users/phone_input.html'

    def get(self, request):
        # Если пользователь уже авторизован - редиректим в профиль
        if request.user.is_authenticated:
            return redirect('users:profile')
        form = PhoneForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = PhoneForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']

            # Генерируем SMS-код
            sms_code = SMSCode.generate_code(phone, expires_minutes=5)

            # Сохраняем телефон в сессии для следующего шага
            request.session['pending_phone'] = phone

            # ИМИТАЦИЯ ОТПРАВКИ SMS
            print(f"\n{'=' * 50}")
            print(f"📱 SMS для {phone}")
            print(f"Ваш код подтверждения: {sms_code.code}")
            print(f"{'=' * 50}\n")

            # В DEBUG режиме показываем код в сообщении
            if settings.DEBUG:
                messages.info(request, f'📱 DEBUG: Ваш код — <strong>{sms_code.code}</strong>')
            else:
                messages.success(request, 'Код отправлен на ваш номер телефона')

            return redirect('users:verify_code')

        return render(request, self.template_name, {'form': form})


class VerifyCodeView(View):
    """
    Шаг 2: Ввод SMS-кода.
    При успехе — создает/находит пользователя и логинит.
    """
    template_name = 'users/verify_code.html'

    def get(self, request):
        # Проверяем, что телефон был введен ранее
        if 'pending_phone' not in request.session:
            messages.warning(request, 'Сначала введите номер телефона')
            return redirect('users:phone_input')

        form = SMSCodeForm()
        return render(request, self.template_name, {
            'form': form,
            'phone': request.session['pending_phone']
        })

    def post(self, request):
        if 'pending_phone' not in request.session:
            messages.warning(request, 'Сначала введите номер телефона')
            return redirect('users:phone_input')

        phone = request.session['pending_phone']
        form = SMSCodeForm(request.POST)

        if form.is_valid():
            code = form.cleaned_data['code']

            # Ищем последний неиспользованный код
            sms_code = SMSCode.objects.filter(
                phone=phone,
                is_used=False
            ).order_by('-created_at').first()

            # Проверяем код
            if not sms_code:
                messages.error(request, 'Код не найден или уже использован')
                return render(request, self.template_name, {
                    'form': form,
                    'phone': phone
                })

            if not sms_code.is_valid():
                messages.error(request, 'Код истек. Запросите новый')
                return redirect('users:phone_input')

            if sms_code.code != code:
                messages.error(request, 'Неверный код')
                return render(request, self.template_name, {
                    'form': form,
                    'phone': phone
                })

            # Код верный — помечаем как использованный
            sms_code.mark_as_used()

            # Получаем или создаем пользователя
            user, created = User.objects.get_or_create(phone=phone)

            # Логиним пользователя (используем сессионную аутентификацию)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # Очищаем сессию
            del request.session['pending_phone']

            if created:
                messages.success(request, 'Регистрация успешна! Добро пожаловать!')
            else:
                messages.success(request, 'Вы успешно вошли в систему!')

            return redirect('users:profile')

        return render(request, self.template_name, {
            'form': form,
            'phone': phone
        })


# ============================================================
# АВТОРИЗОВАННЫЕ VIEWS (требуют входа)
# ============================================================

class ProfileView(LoginRequiredMixin, TemplateView):
    """Страница профиля пользователя"""
    template_name = 'users/profile.html'
    login_url = 'users:phone_input'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Список приглашенных пользователей
        invited_users = User.objects.filter(invited_by=user)

        context['invited_users'] = invited_users
        context['invited_count'] = invited_users.count()

        # Форма для ввода инвайт-кода (если еще не использован)
        if user.invited_by is None:
            context['invite_form'] = InviteCodeForm()

        return context


class ApplyInviteView(LoginRequiredMixin, View):
    """Обработка ввода инвайт-кода"""
    login_url = 'users:phone_input'

    def post(self, request):
        form = InviteCodeForm(request.POST)

        if form.is_valid():
            invite_code = form.cleaned_data['invite_code']
            user = request.user

            # Проверка: уже использовал инвайт?
            if user.invited_by is not None:
                messages.error(request, 'Вы уже активировали инвайт-код')
                return redirect('users:profile')

            # Поиск пригласившего
            try:
                inviter = User.objects.get(invite_code=invite_code)
            except User.DoesNotExist:
                messages.error(request, 'Инвайт-код не найден')
                return redirect('users:profile')

            # Нельзя использовать свой код
            if inviter == user:
                messages.error(request, 'Нельзя использовать свой собственный код')
                return redirect('users:profile')

            # Устанавливаем связь
            user.invited_by = inviter
            user.save()

            messages.success(request, f'Инвайт-код успешно активирован! Вас пригласил {inviter.phone}')
            return redirect('users:profile')

        messages.error(request, 'Неверный формат инвайт-кода')
        return redirect('users:profile')
