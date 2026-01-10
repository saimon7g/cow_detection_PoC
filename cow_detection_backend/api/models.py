from django.db import models
from django.contrib.auth.models import User


class CowProfile(models.Model):
    """Model to store cow registration information."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cow_profiles')
    policy_id = models.CharField(max_length=100, help_text="Policy/registration ID (unique together with cow_name)")
    cow_name = models.CharField(max_length=100)
    cow_age = models.IntegerField(null=True, blank=True, help_text="Age of the cow in months or years")
    cow_breed = models.CharField(max_length=100, blank=True, help_text="Breed of the cow")
    owner_name = models.CharField(max_length=200, blank=True, help_text="Name of the cow owner")
    cow_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['policy_id', 'cow_name']]
    
    def __str__(self):
        return f"{self.cow_name} (Policy: {self.policy_id})"


class TrainingStatus(models.Model):
    """Model to track ML training status for each cow registration."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    cow_profile = models.OneToOneField(CowProfile, on_delete=models.CASCADE, related_name='training_status')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    num_images = models.IntegerField(null=True, blank=True)
    epochs = models.IntegerField(null=True, blank=True)
    checkpoint_path = models.CharField(max_length=500, blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Training {self.status} for {self.cow_profile.cow_name}"

