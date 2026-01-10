from django.contrib import admin
from .models import CowProfile, TrainingStatus


@admin.register(CowProfile)
class CowProfileAdmin(admin.ModelAdmin):
    list_display = ('policy_id', 'cow_name', 'owner_name', 'cow_breed', 'cow_age', 'user', 'created_at')
    list_filter = ('created_at', 'cow_breed', 'cow_age')
    search_fields = ('policy_id', 'cow_name', 'owner_name', 'cow_id', 'user__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TrainingStatus)
class TrainingStatusAdmin(admin.ModelAdmin):
    list_display = ('cow_profile', 'status', 'started_at', 'completed_at', 'num_images', 'epochs')
    list_filter = ('status', 'started_at')
    search_fields = ('cow_profile__cow_name', 'cow_profile__policy_id')
    readonly_fields = ('started_at', 'completed_at')

