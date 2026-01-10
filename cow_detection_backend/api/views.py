from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.conf import settings
from pathlib import Path
import os
import shutil
import threading
import traceback
import logging
from .serializers import CowRegistrationSerializer, UserSerializer, CowProfileSerializer, TrainingStatusSerializer
from .models import CowProfile, TrainingStatus
from .training_service import train_cow_incremental

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register a cow with all information and automatic ML training using muzzle photos.
    
    Expected payload (multipart/form-data):
    - policy_id: string (required) - Unique policy/registration ID
    - cow_name: string (required)
    - cow_age: integer (optional)
    - cow_breed: string (optional)
    - owner_name: string (optional)
    - cow_id: string (optional)
    - cow_photos: multiple image files (optional) - General cow photos (saved but not used for training)
      Send multiple files: -F "cow_photos=@photo1.jpg" -F "cow_photos=@photo2.jpg"
    - muzzle_photos: multiple image files (required if train_model=True) - Used for ML training
      Send multiple files: -F "muzzle_photos=@muzzle1.jpg" -F "muzzle_photos=@muzzle2.jpg"
    - train_model: boolean (default: True)
    - epochs: integer (default: 50)
    - batch_size: integer (default: 8)
    - contrastive_weight: float (default: 0.8)
    
    Optional user fields (if creating new user):
    - username: string (optional)
    - email: string (optional)
    - password: string (optional, min 8 chars)
    - password_confirm: string (optional)
    - first_name: string (optional)
    - last_name: string (optional)
    """
    # Extract multiple files as arrays from request.FILES
    # When same field name is used multiple times, getlist() returns all values
    cow_photos_list = request.FILES.getlist('cow_photos', [])
    muzzle_photos_list = request.FILES.getlist('muzzle_photos', [])
    
    # Create a mutable copy of request.data without files (to avoid deepcopy issues)
    # Build a new dict with non-file data, then add file lists
    from django.http import QueryDict
    data = QueryDict(mutable=True)
    
    # Copy all non-file fields
    for key, value in request.data.items():
        if key not in ['cow_photos', 'muzzle_photos']:
            if isinstance(value, list):
                data.setlist(key, value)
            else:
                data[key] = value
    
    # Add file lists
    if cow_photos_list:
        for photo in cow_photos_list:
            data.appendlist('cow_photos', photo)
    if muzzle_photos_list:
        for photo in muzzle_photos_list:
            data.appendlist('muzzle_photos', photo)
    
    serializer = CowRegistrationSerializer(data=data)
    
    if serializer.is_valid():
        cow_profile = serializer.save()
        
        # Prepare response data
        # Check if this was a new registration or update
        is_new = not hasattr(cow_profile, '_was_existing') or not getattr(cow_profile, '_was_existing', False)
        
        response_data = {
            'message': 'Cow registered successfully' if is_new else 'Cow updated successfully',
            'cow_profile': CowProfileSerializer(cow_profile).data,
            'user': UserSerializer(cow_profile.user).data,
            'is_new_registration': is_new,
        }
        
        # Handle photo saving and ML training
        # Get photos from the saved profile or directly from request
        muzzle_photos = getattr(cow_profile, '_muzzle_photos', muzzle_photos_list)
        cow_photos = getattr(cow_profile, '_cow_photos', cow_photos_list)
        train_model = getattr(cow_profile, '_train_model', False)
        
        try:
            # Create directories for photos
            policy_id = cow_profile.policy_id
            cow_name = cow_profile.cow_name
            
            # Directory for general cow photos
            cow_photos_dir = Path(settings.COW_IMAGES_DIR) / policy_id / "cow_photos"
            cow_photos_dir.mkdir(parents=True, exist_ok=True)
            
            # Directory for muzzle photos (used for training)
            muzzle_photos_dir = Path(settings.COW_IMAGES_DIR) / policy_id / "muzzle_photos"
            muzzle_photos_dir.mkdir(parents=True, exist_ok=True)
            
            # Save general cow photos
            saved_cow_photos = []
            for idx, image_file in enumerate(cow_photos):
                file_extension = Path(image_file.name).suffix or '.jpg'
                filename = f"{cow_name}_cow_{idx+1}{file_extension}"
                file_path = cow_photos_dir / filename
                
                with open(file_path, 'wb') as f:
                    for chunk in image_file.chunks():
                        f.write(chunk)
                saved_cow_photos.append(str(file_path))
            
            # Save muzzle photos (these will be used for training)
            saved_muzzle_photos = []
            for idx, image_file in enumerate(muzzle_photos):
                file_extension = Path(image_file.name).suffix or '.jpg'
                filename = f"{cow_name}_muzzle_{idx+1}{file_extension}"
                file_path = muzzle_photos_dir / filename
                
                with open(file_path, 'wb') as f:
                    for chunk in image_file.chunks():
                        f.write(chunk)
                saved_muzzle_photos.append(str(file_path))
            
            response_data['photos'] = {
                'cow_photos_saved': len(saved_cow_photos),
                'muzzle_photos_saved': len(saved_muzzle_photos),
                'cow_photos_directory': str(cow_photos_dir),
                'muzzle_photos_directory': str(muzzle_photos_dir),
            }
            
            # Handle training asynchronously
            if train_model and saved_muzzle_photos:
                # Create training status record
                training_status, _ = TrainingStatus.objects.get_or_create(
                    cow_profile=cow_profile,
                    defaults={'status': 'pending'}
                )
                training_status.status = 'pending'
                training_status.error_message = ''
                training_status.save()
                
                # Start training in background thread
                def run_training_async():
                    try:
                        training_status.status = 'running'
                        training_status.save()
                        
                        training_result = train_cow_incremental(
                            cow_images_dir=muzzle_photos_dir,
                            cow_name=cow_name,
                            epochs=getattr(cow_profile, '_epochs', 50),
                            batch_size=getattr(cow_profile, '_batch_size', 8),
                            contrastive_weight=getattr(cow_profile, '_contrastive_weight', 0.8),
                        )
                        
                        # Update training status on success
                        training_status.status = 'completed'
                        training_status.num_images = training_result['num_images']
                        training_status.epochs = training_result['epochs']
                        training_status.checkpoint_path = training_result['checkpoint_path']
                        from django.utils import timezone
                        training_status.completed_at = timezone.now()
                        training_status.save()
                        
                        logger.info(f"Training completed for {cow_name}")
                        
                    except Exception as e:
                        training_status.status = 'failed'
                        training_status.error_message = str(e)
                        from django.utils import timezone
                        training_status.completed_at = timezone.now()
                        training_status.save()
                        import traceback as tb
                        logger.error(f"Training failed for {cow_name}: {tb.format_exc()}")
                
                # Start training in background thread
                training_thread = threading.Thread(target=run_training_async, daemon=True)
                training_thread.start()
                
                response_data['training'] = {
                    'status': 'started',
                    'message': 'Training started in background',
                    'training_status_id': training_status.id,
                    'check_status_url': f'/api/training-status/{training_status.id}/',
                }
                response_data['message'] = 'Cow registered successfully. Training started in background.'
                
            elif train_model and not saved_muzzle_photos:
                response_data['training'] = {
                    'status': 'skipped',
                    'reason': 'No muzzle photos provided for training',
                }
        
        except Exception as e:
            response_data['photos'] = {
                'status': 'failed',
                'error': str(e),
            }
            import traceback
            print(f"Photo saving error: {traceback.format_exc()}")
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def user_info(request):
    """Get current user information."""
    if request.user.is_authenticated:
        serializer = UserSerializer(request.user)
        cow_profiles = CowProfile.objects.filter(user=request.user)
        cow_serializer = CowProfileSerializer(cow_profiles, many=True)
        
        return Response({
            'user': serializer.data,
            'cow_profiles': cow_serializer.data
        })
    return Response({'error': 'Not authenticated'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@permission_classes([AllowAny])
def training_status(request, training_id):
    """Get training status for a specific training job."""
    try:
        training_status_obj = TrainingStatus.objects.get(id=training_id)
        serializer = TrainingStatusSerializer(training_status_obj)
        return Response(serializer.data)
    except TrainingStatus.DoesNotExist:
        return Response({'error': 'Training status not found'}, status=status.HTTP_404_NOT_FOUND)

