from django.contrib import admin
from django.urls import path, include
from pedidos import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard_principal, name='dashboard'), 
    path('pedidos/', include('pedidos.urls')),
]