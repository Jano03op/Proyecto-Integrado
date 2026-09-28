from django.urls import path

from . import views

app_name = 'organizacion'

urlpatterns = [
    path('delegaciones/', views.delegaciones_list, name='delegaciones_list'),
    path('delegaciones/nueva/', views.delegacion_create, name='delegacion_create'),
    path('delegaciones/<int:pk>/', views.delegacion_detail, name='delegacion_detail'),
    path('delegaciones/<int:pk>/editar/', views.delegacion_edit, name='delegacion_edit'),
    path('delegaciones/<int:pk>/toggle-estado/', views.delegacion_toggle_estado, name='delegacion_toggle_estado'),
]
