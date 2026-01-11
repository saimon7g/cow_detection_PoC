from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('profiles/', views.list_profiles, name='list_profiles'),
    path('classify/', views.classify_cow, name='classify_cow'),
    path('user/', views.user_info, name='user_info'),
    path('training-status/<int:training_id>/', views.training_status, name='training_status'),
]

