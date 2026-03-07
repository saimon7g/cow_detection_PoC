from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import (
    RetrieveAPIView,
    ListAPIView,
    CreateAPIView,
    ListCreateAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from django.http import QueryDict
from pathlib import Path
import threading
import traceback
import logging

from .serializers import (
    CustomTokenObtainPairSerializer,
    CowRegistrationSerializer,
    UserSerializer,
    CowProfileSerializer,
    CowProfileListSerializer,
    TrainingStatusSerializer,
    CowClassificationSerializer,
    FarmerCreateSerializer,
    InsuranceClaimSerializer,
    InsuranceClaimCreateSerializer,
    InsuranceClaimAssignSerializer,
    InsuranceClaimVerifySerializer,
    InsuranceClaimApproveSerializer,
    AdminFarmerSerializer,
    AdminAgentSerializer,
)
from .models import CowProfile, TrainingStatus, UserProfile, InsuranceClaim
from .permissions import (
    IsCompanyAgent,
    IsFarmer,
    IsAdminUser,
    IsCompanyAgentOrFarmer,
    IsCompanyAgentOrAdmin,
    is_farmer,
)
from .training_service import train_cow_incremental
from .classification_service import classify_cow_image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JWT login
# ---------------------------------------------------------------------------

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# ---------------------------------------------------------------------------
# User info
# ---------------------------------------------------------------------------

class UserInfoView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


# ---------------------------------------------------------------------------
# Farmer management (company agent only)
# ---------------------------------------------------------------------------

@extend_schema(request=FarmerCreateSerializer, responses={201: UserSerializer})
class CreateFarmerView(CreateAPIView):
    permission_classes = [IsCompanyAgent]
    serializer_class = FarmerCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'message': 'Farmer created successfully.',
                'farmer': UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ListFarmersView(ListAPIView):
    permission_classes = [IsCompanyAgent]
    serializer_class = AdminFarmerSerializer

    def get_queryset(self):
        return User.objects.filter(profile__user_type='farmer').order_by('username')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'farmers': serializer.data})


# ---------------------------------------------------------------------------
# Cow registration (company agent only)
# ---------------------------------------------------------------------------

@extend_schema(request=CowRegistrationSerializer, responses={201: CowProfileSerializer})
class RegisterCowView(APIView):
    permission_classes = [IsCompanyAgent]

    def post(self, request):
        cow_photos_list = request.FILES.getlist('cow_photos', [])
        muzzle_photos_list = request.FILES.getlist('muzzle_photos', [])

        data = QueryDict(mutable=True)
        for key, value in request.data.items():
            if key not in ['cow_photos', 'muzzle_photos']:
                if isinstance(value, list):
                    data.setlist(key, value)
                else:
                    data[key] = value
        for photo in cow_photos_list:
            data.appendlist('cow_photos', photo)
        for photo in muzzle_photos_list:
            data.appendlist('muzzle_photos', photo)

        serializer = CowRegistrationSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cow_profile = serializer.save()

        response_data = {
            'message': 'Cow registered successfully.',
            'cow_profile': CowProfileSerializer(cow_profile).data,
            'farmer': UserSerializer(cow_profile.user).data,
        }

        muzzle_photos = getattr(cow_profile, '_muzzle_photos', [])
        cow_photos = getattr(cow_profile, '_cow_photos', [])
        train_model = getattr(cow_profile, '_train_model', False)

        try:
            policy_id = cow_profile.policy_id
            cow_name = cow_profile.cow_name

            cow_photos_dir = Path(settings.COW_IMAGES_DIR) / policy_id / "cow_photos"
            cow_photos_dir.mkdir(parents=True, exist_ok=True)
            muzzle_photos_dir = Path(settings.COW_IMAGES_DIR) / policy_id / "muzzle_photos"
            muzzle_photos_dir.mkdir(parents=True, exist_ok=True)

            saved_cow_photos = []
            for idx, image_file in enumerate(cow_photos):
                ext = Path(image_file.name).suffix or '.jpg'
                fp = cow_photos_dir / f"{cow_name}_cow_{idx+1}{ext}"
                with open(fp, 'wb') as f:
                    for chunk in image_file.chunks():
                        f.write(chunk)
                saved_cow_photos.append(str(fp))

            saved_muzzle_photos = []
            for idx, image_file in enumerate(muzzle_photos):
                ext = Path(image_file.name).suffix or '.jpg'
                fp = muzzle_photos_dir / f"{cow_name}_muzzle_{idx+1}{ext}"
                with open(fp, 'wb') as f:
                    for chunk in image_file.chunks():
                        f.write(chunk)
                saved_muzzle_photos.append(str(fp))

            response_data['photos'] = {
                'cow_photos_saved': len(saved_cow_photos),
                'muzzle_photos_saved': len(saved_muzzle_photos),
            }

            if train_model and saved_muzzle_photos:
                ts, _ = TrainingStatus.objects.get_or_create(
                    cow_profile=cow_profile, defaults={'status': 'pending'}
                )
                ts.status = 'pending'
                ts.error_message = ''
                ts.save()

                def run_training():
                    try:
                        ts.status = 'running'
                        ts.save()
                        result = train_cow_incremental(
                            cow_images_dir=muzzle_photos_dir,
                            cow_name=cow_name,
                            epochs=getattr(cow_profile, '_epochs', 50),
                            batch_size=getattr(cow_profile, '_batch_size', 8),
                            contrastive_weight=getattr(cow_profile, '_contrastive_weight', 0.8),
                        )
                        ts.status = 'completed'
                        ts.num_images = result['num_images']
                        ts.epochs = result['epochs']
                        ts.checkpoint_path = result['checkpoint_path']
                        ts.completed_at = timezone.now()
                        ts.save()
                        logger.info(f"Training completed for {cow_name}")
                    except Exception as exc:
                        ts.status = 'failed'
                        ts.error_message = str(exc)
                        ts.completed_at = timezone.now()
                        ts.save()
                        logger.error(f"Training failed for {cow_name}: {traceback.format_exc()}")

                threading.Thread(target=run_training, daemon=True).start()
                response_data['training'] = {
                    'status': 'started',
                    'training_status_id': ts.id,
                    'check_status_url': f'/api/training-status/{ts.id}/',
                }
            elif train_model:
                response_data['training'] = {'status': 'skipped', 'reason': 'No muzzle photos provided.'}

        except Exception as exc:
            response_data['photos'] = {'status': 'failed', 'error': str(exc)}
            logger.error(f"Photo saving error: {traceback.format_exc()}")

        return Response(response_data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Cow profile listing
# ---------------------------------------------------------------------------

class ListProfilesView(ListAPIView):
    permission_classes = [IsCompanyAgentOrAdmin]
    serializer_class = CowProfileListSerializer
    queryset = CowProfile.objects.all().order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'profiles': serializer.data})


class MyCowsView(ListAPIView):
    permission_classes = [IsFarmer]
    serializer_class = CowProfileSerializer

    def get_queryset(self):
        return CowProfile.objects.filter(user=self.request.user).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'cows': serializer.data})


# ---------------------------------------------------------------------------
# Training status
# ---------------------------------------------------------------------------

@extend_schema(responses={200: TrainingStatusSerializer, 404: None})
class TrainingStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, training_id):
        try:
            ts = TrainingStatus.objects.get(id=training_id)
        except TrainingStatus.DoesNotExist:
            return Response({'error': 'Training status not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(TrainingStatusSerializer(ts).data)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

@extend_schema(request=CowClassificationSerializer, responses={200: None, 503: None})
class ClassifyCowView(APIView):
    permission_classes = [IsCompanyAgentOrAdmin]

    def post(self, request):
        serializer = CowClassificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_file = serializer.validated_data['image']
        top_k = serializer.validated_data.get('top_k', 5)
        threshold = serializer.validated_data.get('threshold', None)

        try:
            matches = classify_cow_image(image_file=image_file, top_k=top_k, threshold=threshold)
            enriched = []
            for match in matches:
                cow_profile = CowProfile.objects.filter(
                    cow_name=match['cow_name']
                ).order_by('-created_at').first()
                match['cow_profile'] = CowProfileSerializer(cow_profile).data if cow_profile else None
                enriched.append(match)

            best = enriched[0] if enriched else None
            verdict = {
                'matched': best is not None,
                'best_match': best,
                'confidence': (
                    'high' if best and best['distance'] < 0.5 else
                    'medium' if best and best['distance'] < 1.0 else
                    'low' if best else None
                ),
            }
            return Response({
                'message': 'Classification completed successfully.',
                'verdict': verdict,
                'all_matches': enriched,
                'total_matches': len(enriched),
            })

        except FileNotFoundError:
            return Response(
                {'error': 'Model checkpoint not found. Train the model first.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.error(f"Classification error: {traceback.format_exc()}")
            return Response({'error': 'Classification failed.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Insurance claims
# ---------------------------------------------------------------------------

@extend_schema(
    request=InsuranceClaimCreateSerializer,
    responses={200: InsuranceClaimSerializer(many=True), 201: InsuranceClaimSerializer},
)
class ClaimsListCreateView(ListCreateAPIView):
    permission_classes = [IsCompanyAgentOrFarmer]

    def get_queryset(self):
        if is_farmer(self.request.user):
            qs = InsuranceClaim.objects.filter(cow_profile__user=self.request.user)
        else:
            qs = InsuranceClaim.objects.all()

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        cow_profile_id = self.request.query_params.get('cow_profile_id')
        if cow_profile_id:
            qs = qs.filter(cow_profile_id=cow_profile_id)
        return qs

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return InsuranceClaimCreateSerializer
        return InsuranceClaimSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = InsuranceClaimSerializer(queryset, many=True)
        return Response({'count': queryset.count(), 'claims': serializer.data})

    def create(self, request, *args, **kwargs):
        serializer = InsuranceClaimCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cow_profile_id = serializer.validated_data['cow_profile_id']
        cow_profile = CowProfile.objects.get(id=cow_profile_id)

        if is_farmer(request.user) and cow_profile.user != request.user:
            return Response(
                {'error': 'You can only create claims for your own cows.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        claim = InsuranceClaim.objects.create(
            cow_profile=cow_profile,
            reason=serializer.validated_data['reason'],
            notes=serializer.validated_data.get('notes', ''),
            created_by=request.user,
            status='pending',
        )
        return Response(
            {'message': 'Claim created successfully.', 'claim': InsuranceClaimSerializer(claim).data},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(request=InsuranceClaimAssignSerializer, responses={200: InsuranceClaimSerializer, 404: None})
class ClaimAssignView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, claim_id):
        try:
            claim = InsuranceClaim.objects.get(id=claim_id)
        except InsuranceClaim.DoesNotExist:
            return Response({'error': 'Claim not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InsuranceClaimAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        agent = User.objects.get(id=serializer.validated_data['agent_id'])
        claim.assigned_to = agent
        claim.assigned_at = timezone.now()
        claim.assigned_by = request.user
        claim.save()

        return Response({
            'message': f'Claim #{claim.id} assigned to agent {agent.username}.',
            'claim': InsuranceClaimSerializer(claim).data,
        })


@extend_schema(request=InsuranceClaimVerifySerializer, responses={200: InsuranceClaimSerializer, 403: None, 404: None})
class ClaimVerifyView(APIView):
    permission_classes = [IsCompanyAgent]

    def post(self, request, claim_id):
        try:
            claim = InsuranceClaim.objects.get(id=claim_id)
        except InsuranceClaim.DoesNotExist:
            return Response({'error': 'Claim not found.'}, status=status.HTTP_404_NOT_FOUND)

        if claim.assigned_to != request.user:
            return Response(
                {'error': 'You are not assigned to verify this claim.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = InsuranceClaimVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        claim.verification_result = serializer.validated_data['verification_result']
        claim.verification_notes = serializer.validated_data.get('verification_notes', '')
        claim.verified_at = timezone.now()
        claim.verified_by = request.user
        claim.save()

        return Response({
            'message': 'Verification recorded.',
            'claim': InsuranceClaimSerializer(claim).data,
        })


@extend_schema(request=InsuranceClaimApproveSerializer, responses={200: InsuranceClaimSerializer, 404: None})
class ClaimApproveView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, claim_id):
        try:
            claim = InsuranceClaim.objects.get(id=claim_id)
        except InsuranceClaim.DoesNotExist:
            return Response({'error': 'Claim not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InsuranceClaimApproveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']
        claim.status = 'approved' if action == 'approve' else 'rejected'
        claim.approval_notes = serializer.validated_data.get('approval_notes', '')
        claim.approved_at = timezone.now()
        claim.approved_by = request.user
        claim.save()

        return Response({
            'message': f'Claim #{claim.id} has been {claim.status}.',
            'claim': InsuranceClaimSerializer(claim).data,
        })


# ---------------------------------------------------------------------------
# Admin – read-only information endpoints
# ---------------------------------------------------------------------------

@extend_schema(responses={200: None}, description='Aggregate stats: total cows, agents, farmers, claim counts.')
class AdminDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_cows = CowProfile.objects.count()
        total_agents = UserProfile.objects.filter(user_type='company_agent').count()
        total_farmers = UserProfile.objects.filter(user_type='farmer').count()
        claims_pending = InsuranceClaim.objects.filter(status='pending').count()
        claims_approved = InsuranceClaim.objects.filter(status='approved').count()
        claims_rejected = InsuranceClaim.objects.filter(status='rejected').count()
        claims_unassigned = InsuranceClaim.objects.filter(assigned_to__isnull=True, status='pending').count()
        claims_verified = InsuranceClaim.objects.filter(verification_result__isnull=False).count()

        return Response({
            'total_registered_cows': total_cows,
            'total_company_agents': total_agents,
            'total_farmers': total_farmers,
            'claims': {
                'pending': claims_pending,
                'approved': claims_approved,
                'rejected': claims_rejected,
                'unassigned_pending': claims_unassigned,
                'verified_by_agent': claims_verified,
            },
        })


class AdminCompanyAgentsView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminAgentSerializer

    def get_queryset(self):
        return User.objects.filter(profile__user_type='company_agent').order_by('username')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'company_agents': serializer.data})


class AdminFarmersView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminFarmerSerializer

    def get_queryset(self):
        return User.objects.filter(profile__user_type='farmer').order_by('username')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'farmers': serializer.data})


class AdminClaimsView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = InsuranceClaimSerializer

    def get_queryset(self):
        qs = InsuranceClaim.objects.all()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        verified_by = self.request.query_params.get('verified_by')
        if verified_by:
            qs = qs.filter(verified_by_id=verified_by)
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)
        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'claims': serializer.data})
