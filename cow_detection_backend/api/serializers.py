from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import IntegrityError
import uuid
from datetime import datetime
from .models import CowProfile, TrainingStatus


class CowRegistrationSerializer(serializers.Serializer):
    """Serializer for cow registration with all required information."""
    # User fields (optional - can create user or use existing)
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    
    # Cow information (required)
    # policy_id is now generated server-side, not accepted from client
    cow_name = serializers.CharField(max_length=100, required=True)
    cow_age = serializers.IntegerField(required=False, allow_null=True, help_text="Age in months or years")
    cow_breed = serializers.CharField(max_length=100, required=False, allow_blank=True)
    owner_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    # cow_id is now generated server-side, not accepted from client
    
    # Photo fields - accept multiple files as arrays
    cow_photos = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="Array of general cow photos (saved but not used for training). Send multiple files with same field name."
    )
    muzzle_photos = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="Array of muzzle photos (used for ML training). Send multiple files with same field name."
    )
    
    # Training parameters
    train_model = serializers.BooleanField(write_only=True, default=True)
    epochs = serializers.IntegerField(write_only=True, default=50, required=False)
    batch_size = serializers.IntegerField(write_only=True, default=8, required=False)
    contrastive_weight = serializers.FloatField(write_only=True, default=0.8, required=False)
    
    def validate(self, attrs):
        # Validate password if provided
        if attrs.get('password'):
            if attrs.get('password') != attrs.get('password_confirm'):
                raise serializers.ValidationError({"password": "Passwords do not match."})
        
        # If train_model is True, muzzle_photos are required
        if attrs.get('train_model', False):
            muzzle_photos = attrs.get('muzzle_photos', [])
            if not muzzle_photos or len(muzzle_photos) < 1:
                raise serializers.ValidationError({
                    "muzzle_photos": "At least one muzzle photo is required for training."
                })
        
        return attrs
    
    def create(self, validated_data):
        # Extract user fields
        username = validated_data.pop('username', None)
        email = validated_data.pop('email', '')
        password = validated_data.pop('password', None)
        password_confirm = validated_data.pop('password_confirm', None)
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        
        # Extract cow information
        cow_name = validated_data.pop('cow_name')
        
        # Generate unique policy_id server-side
        # Format: POL-YYYYMMDD-HHMMSS-{short_uuid}
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        short_uuid = str(uuid.uuid4())[:8].upper()
        policy_id = f"POL-{timestamp}-{short_uuid}"
        
        # Generate unique cow_id server-side
        # Format: COW-YYYYMMDD-HHMMSS-{short_uuid}
        cow_uuid = str(uuid.uuid4())[:8].upper()
        cow_id = f"COW-{timestamp}-{cow_uuid}"
        
        cow_age = validated_data.pop('cow_age', None)
        cow_breed = validated_data.pop('cow_breed', '')
        owner_name = validated_data.pop('owner_name', '')
        
        # Extract photo fields
        cow_photos = validated_data.pop('cow_photos', [])
        muzzle_photos = validated_data.pop('muzzle_photos', [])
        
        # Extract training parameters
        train_model = validated_data.pop('train_model', False)
        epochs = validated_data.pop('epochs', 50)
        batch_size = validated_data.pop('batch_size', 8)
        contrastive_weight = validated_data.pop('contrastive_weight', 0.8)
        
        # Create or get user (if username not provided, create a default user)
        if username:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                }
            )
            if created and password:
                user.set_password(password)
                user.save()
        else:
            # Create a default user based on cow_name or generate unique username
            default_username = f"user_{cow_name.lower().replace(' ', '_')}_{short_uuid}"
            user, created = User.objects.get_or_create(
                username=default_username,
                defaults={
                    'email': email or f"{default_username}@example.com",
                    'first_name': owner_name or first_name,
                    'last_name': last_name,
                }
            )
            if created and password:
                user.set_password(password)
                user.save()
        
        # Create or get cow profile with all information
        # Use get_or_create with both policy_id and cow_name (unique_together constraint)
        # Generate unique cow_id - keep trying until we get a unique one
        max_retries = 5
        cow_id_to_use = cow_id
        for attempt in range(max_retries):
            existing_cow_with_id = CowProfile.objects.filter(cow_id=cow_id_to_use).first()
            if not existing_cow_with_id:
                break  # Found a unique cow_id
            # Generate a new one if it conflicts
            cow_uuid = str(uuid.uuid4())[:8].upper()
            cow_id_to_use = f"COW-{timestamp}-{cow_uuid}"
        
        defaults = {
            'user': user,
            'cow_age': cow_age,
            'cow_breed': cow_breed,
            'owner_name': owner_name,
            'cow_id': cow_id_to_use,
        }
        
        try:
            cow_profile, created = CowProfile.objects.get_or_create(
                policy_id=policy_id,
                cow_name=cow_name,
                defaults=defaults
            )
            
            if not created:
                # Cow already exists - update the fields
                cow_profile.cow_age = cow_age if cow_age is not None else cow_profile.cow_age
                cow_profile.cow_breed = cow_breed if cow_breed else cow_profile.cow_breed
                cow_profile.owner_name = owner_name if owner_name else cow_profile.owner_name
                cow_profile.user = user  # Update user in case it changed
                cow_profile.save()
                cow_profile._was_existing = True  # Mark as existing for view
            else:
                cow_profile._was_existing = False  # Mark as new for view
        except IntegrityError:
            # If there's still a conflict (race condition), retry without cow_id first, then generate new one
            defaults.pop('cow_id', None)
            cow_profile, created = CowProfile.objects.get_or_create(
                policy_id=policy_id,
                cow_name=cow_name,
                defaults=defaults
            )
            # Generate and set cow_id after creation
            if created:
                # Generate unique cow_id
                for attempt in range(max_retries):
                    cow_uuid = str(uuid.uuid4())[:8].upper()
                    new_cow_id = f"COW-{timestamp}-{cow_uuid}"
                    if not CowProfile.objects.filter(cow_id=new_cow_id).exists():
                        cow_profile.cow_id = new_cow_id
                        cow_profile.save()
                        break
            else:
                cow_profile.cow_age = cow_age if cow_age is not None else cow_profile.cow_age
                cow_profile.cow_breed = cow_breed if cow_breed else cow_profile.cow_breed
                cow_profile.owner_name = owner_name if owner_name else cow_profile.owner_name
                cow_profile.user = user
                cow_profile.save()
                cow_profile._was_existing = True
        
        # Store photo and training info for view to handle
        cow_profile._cow_photos = cow_photos
        cow_profile._muzzle_photos = muzzle_photos
        cow_profile._train_model = train_model
        cow_profile._epochs = epochs
        cow_profile._batch_size = batch_size
        cow_profile._contrastive_weight = contrastive_weight
        
        return cow_profile


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user information."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined')


class CowProfileSerializer(serializers.ModelSerializer):
    """Serializer for cow profile."""
    
    class Meta:
        model = CowProfile
        fields = (
            'id', 'policy_id', 'cow_name', 'cow_age', 'cow_breed', 
            'owner_name', 'cow_id', 'created_at', 'updated_at', 'notes'
        )


class TrainingStatusSerializer(serializers.ModelSerializer):
    """Serializer for training status."""
    cow_profile = CowProfileSerializer(read_only=True)
    
    class Meta:
        model = TrainingStatus
        fields = (
            'id', 'cow_profile', 'status', 'started_at', 'completed_at',
            'error_message', 'num_images', 'epochs', 'checkpoint_path'
        )


class CowClassificationSerializer(serializers.Serializer):
    """Serializer for cow image classification."""
    image = serializers.ImageField(required=True, help_text="Cow image to classify")
    top_k = serializers.IntegerField(required=False, default=5, min_value=1, max_value=20, help_text="Number of top matches to return")
    threshold = serializers.FloatField(required=False, allow_null=True, min_value=0.0, help_text="Maximum distance threshold for matches")


class CowMatchSerializer(serializers.Serializer):
    """Serializer for cow match results."""
    cow_name = serializers.CharField()
    distance = serializers.FloatField()
    rank = serializers.IntegerField()
    cow_profile = CowProfileSerializer(read_only=True, allow_null=True)


class CowProfileListSerializer(serializers.ModelSerializer):
    """Serializer for listing cow profiles with minimal fields."""
    
    class Meta:
        model = CowProfile
        fields = ('cow_name', 'cow_breed', 'owner_name', 'policy_id')

