from django.db import models
from django.contrib.auth.models import User


USER_TYPE_CHOICES = [
    ('company_agent', 'Company Agent'),
    ('farmer', 'Farmer'),
    ('admin', 'Admin'),
]


class UserProfile(models.Model):
    """Extends the built-in User with a role (user_type)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)

    def __str__(self):
        return f"{self.user.username} ({self.user_type})"


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


class InsuranceClaim(models.Model):
    """Model to track insurance claims for cows."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    REASON_CHOICES = [
        ('dead', 'Dead'),
        ('sick', 'Sick'),
        ('other', 'Other'),
    ]

    cow_profile = models.ForeignKey(CowProfile, on_delete=models.CASCADE, related_name='claims')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes = models.TextField(blank=True)

    # Submission
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_claims'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    # Assignment (admin assigns an agent to verify)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_claims'
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assignments_made'
    )

    # Verification (agent verifies yes/no, only when assigned)
    verification_result = models.BooleanField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_claims'
    )
    verification_notes = models.TextField(blank=True)

    # Final approval (admin only)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_claims'
    )
    approval_notes = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Claim #{self.id} - {self.cow_profile.cow_name} ({self.status})"
