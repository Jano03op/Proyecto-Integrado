from django.urls import path

from . import views

app_name = 'cuentas'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('registro/', views.registro_view, name='registro'),
    path('recuperar/', views.recuperar_view, name='recuperar'),
    path('inicio/', views.home_view, name='home'),
]
