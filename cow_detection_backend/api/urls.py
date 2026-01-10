from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('user/', views.user_info, name='user_info'),
    path('training-status/<int:training_id>/', views.training_status, name='training_status'),
]

