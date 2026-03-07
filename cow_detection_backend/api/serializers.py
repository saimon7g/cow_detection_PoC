from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count
import uuid
from datetime import datetime
from .models import CowProfile, TrainingStatus, UserProfile, InsuranceClaim


# ---------------------------------------------------------------------------
# JWT – custom token with user_type claim
# ---------------------------------------------------------------------------

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        try:
            token['user_type'] = user.profile.user_type
        except Exception:
            token['user_type'] = None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        try:
            data['user_type'] = self.user.profile.user_type
        except Exception:
            data['user_type'] = None
        data['user_id'] = self.user.id
        data['username'] = self.user.username
        return data


# ---------------------------------------------------------------------------
# User / UserProfile serializers
# ---------------------------------------------------------------------------

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('user_type',)


class UserSerializer(serializers.ModelSerializer):
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'user_type')

    def get_user_type(self, obj):
        try:
            return obj.profile.user_type
        except Exception:
            return None


class FarmerCreateSerializer(serializers.Serializer):
    """Used by company agents to create a farmer account."""
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            password=password,
        )
        UserProfile.objects.create(user=user, user_type='farmer')
        return user


# ---------------------------------------------------------------------------
# Cow profile serializers
# ---------------------------------------------------------------------------

class CowProfileSerializer(serializers.ModelSerializer):
    farmer_username = serializers.SerializerMethodField()

    class Meta:
        model = CowProfile
        fields = (
            'id', 'policy_id', 'cow_name', 'cow_age', 'cow_breed',
            'owner_name', 'cow_id', 'created_at', 'updated_at', 'notes',
            'farmer_username',
        )

    def get_farmer_username(self, obj):
        return obj.user.username


class CowProfileListSerializer(serializers.ModelSerializer):
    farmer_username = serializers.SerializerMethodField()

    class Meta:
        model = CowProfile
        fields = ('id', 'cow_name', 'cow_breed', 'owner_name', 'policy_id', 'cow_id', 'farmer_username')

    def get_farmer_username(self, obj):
        return obj.user.username


class CowRegistrationSerializer(serializers.Serializer):
    """
    Company agents register a cow under a specific farmer (owner_id required).
    No user-creation fields: the farmer must already exist.
    """
    owner_id = serializers.IntegerField(
        help_text="User ID of the farmer who owns this cow."
    )

    cow_name = serializers.CharField(max_length=100)
    cow_age = serializers.IntegerField(required=False, allow_null=True)
    cow_breed = serializers.CharField(max_length=100, required=False, allow_blank=True)
    owner_name = serializers.CharField(max_length=200, required=False, allow_blank=True)

    cow_photos = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False),
        write_only=True, required=False, allow_empty=True,
    )
    muzzle_photos = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False),
        write_only=True, required=False, allow_empty=True,
    )

    train_model = serializers.BooleanField(write_only=True, default=True)
    epochs = serializers.IntegerField(write_only=True, default=50, required=False)
    batch_size = serializers.IntegerField(write_only=True, default=8, required=False)
    contrastive_weight = serializers.FloatField(write_only=True, default=0.8, required=False)

    def validate_owner_id(self, value):
        try:
            owner = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Farmer user not found.")
        try:
            if owner.profile.user_type != 'farmer':
                raise serializers.ValidationError("owner_id must refer to a farmer account.")
        except UserProfile.DoesNotExist:
            raise serializers.ValidationError("The specified user has no role profile.")
        return value

    def validate(self, attrs):
        if attrs.get('train_model', False):
            if not attrs.get('muzzle_photos'):
                raise serializers.ValidationError(
                    {"muzzle_photos": "At least one muzzle photo is required when train_model=true."}
                )
        return attrs

    def create(self, validated_data):
        owner_id = validated_data.pop('owner_id')
        owner = User.objects.get(id=owner_id)

        cow_name = validated_data.pop('cow_name')
        cow_age = validated_data.pop('cow_age', None)
        cow_breed = validated_data.pop('cow_breed', '')
        owner_name = validated_data.pop('owner_name', '') or f"{owner.first_name} {owner.last_name}".strip()
        cow_photos = validated_data.pop('cow_photos', [])
        muzzle_photos = validated_data.pop('muzzle_photos', [])
        train_model = validated_data.pop('train_model', False)
        epochs = validated_data.pop('epochs', 50)
        batch_size = validated_data.pop('batch_size', 8)
        contrastive_weight = validated_data.pop('contrastive_weight', 0.8)

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        short_uuid = str(uuid.uuid4())[:8].upper()
        policy_id = f"POL-{timestamp}-{short_uuid}"

        # Generate unique cow_id
        cow_id = None
        for _ in range(5):
            candidate = f"COW-{timestamp}-{str(uuid.uuid4())[:8].upper()}"
            if not CowProfile.objects.filter(cow_id=candidate).exists():
                cow_id = candidate
                break

        cow_profile = CowProfile.objects.create(
            user=owner,
            policy_id=policy_id,
            cow_name=cow_name,
            cow_age=cow_age,
            cow_breed=cow_breed,
            owner_name=owner_name,
            cow_id=cow_id,
        )

        cow_profile._cow_photos = cow_photos
        cow_profile._muzzle_photos = muzzle_photos
        cow_profile._train_model = train_model
        cow_profile._epochs = epochs
        cow_profile._batch_size = batch_size
        cow_profile._contrastive_weight = contrastive_weight
        return cow_profile


# ---------------------------------------------------------------------------
# Training status
# ---------------------------------------------------------------------------

class TrainingStatusSerializer(serializers.ModelSerializer):
    cow_profile = CowProfileSerializer(read_only=True)

    class Meta:
        model = TrainingStatus
        fields = (
            'id', 'cow_profile', 'status', 'started_at', 'completed_at',
            'error_message', 'num_images', 'epochs', 'checkpoint_path'
        )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class CowClassificationSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)
    top_k = serializers.IntegerField(required=False, default=5, min_value=1, max_value=20)
    threshold = serializers.FloatField(required=False, allow_null=True, min_value=0.0)


class CowMatchSerializer(serializers.Serializer):
    cow_name = serializers.CharField()
    distance = serializers.FloatField()
    rank = serializers.IntegerField()
    cow_profile = CowProfileSerializer(read_only=True, allow_null=True)


# ---------------------------------------------------------------------------
# Insurance claim serializers
# ---------------------------------------------------------------------------

class InsuranceClaimUserSerializer(serializers.ModelSerializer):
    """Minimal user info for embedding inside claims."""
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name')


class InsuranceClaimSerializer(serializers.ModelSerializer):
    cow_profile = CowProfileSerializer(read_only=True)
    created_by = InsuranceClaimUserSerializer(read_only=True)
    assigned_to = InsuranceClaimUserSerializer(read_only=True)
    assigned_by = InsuranceClaimUserSerializer(read_only=True)
    verified_by = InsuranceClaimUserSerializer(read_only=True)
    approved_by = InsuranceClaimUserSerializer(read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = (
            'id', 'cow_profile', 'status', 'reason', 'notes',
            'created_by', 'submitted_at',
            'assigned_to', 'assigned_at', 'assigned_by',
            'verification_result', 'verified_at', 'verified_by', 'verification_notes',
            'approved_at', 'approved_by', 'approval_notes',
            'updated_at',
        )


class InsuranceClaimCreateSerializer(serializers.Serializer):
    cow_profile_id = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=['dead', 'sick', 'other'])
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_cow_profile_id(self, value):
        try:
            CowProfile.objects.get(id=value)
        except CowProfile.DoesNotExist:
            raise serializers.ValidationError("Cow profile not found.")
        return value


class InsuranceClaimAssignSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField()

    def validate_agent_id(self, value):
        try:
            agent = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Agent user not found.")
        try:
            if agent.profile.user_type != 'company_agent':
                raise serializers.ValidationError("agent_id must refer to a company agent.")
        except UserProfile.DoesNotExist:
            raise serializers.ValidationError("The specified user has no role profile.")
        return value


class InsuranceClaimVerifySerializer(serializers.Serializer):
    verification_result = serializers.BooleanField()
    verification_notes = serializers.CharField(required=False, allow_blank=True)


class InsuranceClaimApproveSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    approval_notes = serializers.CharField(required=False, allow_blank=True)


# ---------------------------------------------------------------------------
# Admin serializers
# ---------------------------------------------------------------------------

class AdminFarmerSerializer(serializers.ModelSerializer):
    """Farmer profile with cow count for admin view."""
    cow_count = serializers.SerializerMethodField()
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'user_type', 'cow_count')

    def get_cow_count(self, obj):
        return obj.cow_profiles.count()

    def get_user_type(self, obj):
        try:
            return obj.profile.user_type
        except Exception:
            return None


class AdminAgentSerializer(serializers.ModelSerializer):
    """Company agent profile for admin view."""
    user_type = serializers.SerializerMethodField()
    verified_claims_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'user_type', 'verified_claims_count')

    def get_user_type(self, obj):
        try:
            return obj.profile.user_type
        except Exception:
            return None

    def get_verified_claims_count(self, obj):
        return obj.verified_claims.count()
