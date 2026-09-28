from django.urls import path
from agenda import views

urlpatterns = [
    path('tablero/', views.tablero_agenda, name='tablero_agenda'),
    path('nuevo/', views.crear_compromiso, name='crear_compromiso'),
    path('compromiso/<int:id>/', views.detalle_compromiso, name='detalle_compromiso'),
]
