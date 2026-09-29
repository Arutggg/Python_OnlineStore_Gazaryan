"""URL регистрации, входа и личного кабинета."""

from django.contrib.auth import views as auth_views
from django.urls import path

from users import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    # В Django 5+ выход только через POST — в шаблоне это форма с кнопкой
    path('logout/', auth_views.LogoutView.as_view(template_name='registration/logged_out.html'), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/addresses/add/', views.address_form, name='address_add'),
    path('profile/addresses/<int:pk>/edit/', views.address_form, name='address_edit'),
    path('profile/addresses/<int:pk>/delete/', views.address_delete, name='address_delete'),
]
