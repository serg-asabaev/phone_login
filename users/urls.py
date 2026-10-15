from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from django.contrib.auth.views import LoginView, LogoutView

app_name = 'users'

router = DefaultRouter()
router.register(r'auth/phone', views.PhoneAuthViewSet, basename='phone-auth')

urlpatterns = [
    path('', include(router.urls)),

    # Анонимные страницы
    path('phone_input/', views.PhoneInputView.as_view(), name='phone_input'),
    path('verify/', views.VerifyCodeView.as_view(), name='verify_code'),

    # Авторизованные страницы
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('apply-invite/', views.ApplyInviteView.as_view(), name='apply_invite'),
    path('logout/', LogoutView.as_view(), name='logout'),
]