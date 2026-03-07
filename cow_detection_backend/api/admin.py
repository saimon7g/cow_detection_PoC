from django.contrib import admin
from .models import CowProfile, TrainingStatus, UserProfile, InsuranceClaim


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type')
    list_filter = ('user_type',)
    search_fields = ('user__username', 'user__email')


@admin.register(CowProfile)
class CowProfileAdmin(admin.ModelAdmin):
    list_display = ('policy_id', 'cow_name', 'owner_name', 'cow_breed', 'cow_age', 'user', 'created_at')
    list_filter = ('created_at', 'cow_breed')
    search_fields = ('policy_id', 'cow_name', 'owner_name', 'cow_id', 'user__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TrainingStatus)
class TrainingStatusAdmin(admin.ModelAdmin):
    list_display = ('cow_profile', 'status', 'started_at', 'completed_at', 'num_images', 'epochs')
    list_filter = ('status', 'started_at')
    search_fields = ('cow_profile__cow_name', 'cow_profile__policy_id')
    readonly_fields = ('started_at', 'completed_at')


@admin.register(InsuranceClaim)
class InsuranceClaimAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'cow_profile', 'status', 'reason', 'created_by',
        'assigned_to', 'verification_result', 'verified_by', 'approved_by', 'submitted_at',
    )
    list_filter = ('status', 'reason', 'submitted_at')
    search_fields = ('cow_profile__cow_name', 'cow_profile__policy_id', 'created_by__username')
    readonly_fields = ('submitted_at', 'updated_at', 'verified_at', 'assigned_at', 'approved_at')
