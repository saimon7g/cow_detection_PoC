# Cow Detection API Documentation

## Overview

Single API endpoint to register a cow with complete information including policy details, cow photos, and muzzle photos. The model is trained **ONLY using muzzle photos** asynchronously in the background.

## Endpoints

- **POST** `/api/register/` - Register a cow with all information
- **GET** `/api/training-status/{training_id}/` - Check training status
- **GET** `/api/user/` - Get current user information (requires authentication)

## Register Cow Endpoint

**POST** `/api/register/`

### Request Format

**Content-Type:** `multipart/form-data`

### Required Fields

- `cow_name` (string): Name of the cow
- `muzzle_photos` (files): At least one muzzle photo (required if `train_model=true`)

**Note:** `policy_id` is **automatically generated** server-side and returned in the response. You do not need to provide it in the request.

### Optional Fields

#### Cow Information
- `cow_age` (integer): Age of the cow in months or years
- `cow_breed` (string): Breed of the cow
- `owner_name` (string): Name of the cow owner

**Note:** `cow_id` is **automatically generated** server-side and returned in the response. You do not need to provide it in the request.

#### Photos
- `cow_photos` (files): General cow photos (saved but NOT used for training)
- `muzzle_photos` (files): Muzzle photos (USED for ML training)

#### Training Parameters
- `train_model` (boolean): Whether to train the model (default: `true`)
- `epochs` (integer): Number of training epochs (default: `50`)
- `batch_size` (integer): Batch size for training (default: `8`)
- `contrastive_weight` (float): Weight for contrastive loss (default: `0.8`)

#### User Fields (Optional - for creating new user)
- `username` (string): Username (if not provided, auto-generated from cow_name)
- `email` (string): Email address
- `password` (string): Password (min 8 characters)
- `password_confirm` (string): Password confirmation
- `first_name` (string): First name
- `last_name` (string): Last name

## Example Requests

### Using cURL

```bash
curl -X POST http://127.0.0.1:8000/api/register/ \
  -F "cow_name=Bella" \
  -F "cow_age=24" \
  -F "cow_breed=Holstein" \
  -F "owner_name=John Doe" \
  -F "cow_photos=@/path/to/cow_photo1.jpg" \
  -F "cow_photos=@/path/to/cow_photo2.jpg" \
  -F "muzzle_photos=@/path/to/muzzle1.jpg" \
  -F "muzzle_photos=@/path/to/muzzle2.jpg" \
  -F "muzzle_photos=@/path/to/muzzle3.jpg" \
  -F "train_model=true" \
  -F "epochs=50" \
  -F "batch_size=8" \
  -F "contrastive_weight=0.8"
```

**Note:** Both `policy_id` and `cow_id` are automatically generated and will be returned in the response.

**Note:** Use the same field name multiple times to send multiple files as arrays.

### Using Python requests

```python
import requests

url = "http://127.0.0.1:8000/api/register/"

# Prepare multiple files - each tuple adds one file to the array
files = [
    ('cow_photos', ('cow1.jpg', open('path/to/cow1.jpg', 'rb'), 'image/jpeg')),
    ('cow_photos', ('cow2.jpg', open('path/to/cow2.jpg', 'rb'), 'image/jpeg')),
    ('muzzle_photos', ('muzzle1.jpg', open('path/to/muzzle1.jpg', 'rb'), 'image/jpeg')),
    ('muzzle_photos', ('muzzle2.jpg', open('path/to/muzzle2.jpg', 'rb'), 'image/jpeg')),
    ('muzzle_photos', ('muzzle3.jpg', open('path/to/muzzle3.jpg', 'rb'), 'image/jpeg')),
]

data = {
    'cow_name': 'Bella',
    'cow_age': '24',
    'cow_breed': 'Holstein',
    'owner_name': 'John Doe',
    'train_model': 'true',
    'epochs': '50',
    'batch_size': '8',
    'contrastive_weight': '0.8',
}

response = requests.post(url, files=files, data=data)
print(response.json())
```

### Using JavaScript/Fetch

```javascript
const formData = new FormData();
formData.append('cow_name', 'Bella');
formData.append('cow_age', '24');
formData.append('cow_breed', 'Holstein');
formData.append('owner_name', 'John Doe');
formData.append('train_model', 'true');

// Add multiple cow photos (array)
const cowPhotoFiles = document.getElementById('cowPhotos').files;
for (let i = 0; i < cowPhotoFiles.length; i++) {
    formData.append('cow_photos', cowPhotoFiles[i]);
}

// Add multiple muzzle photos (array)
const muzzlePhotoFiles = document.getElementById('muzzlePhotos').files;
for (let i = 0; i < muzzlePhotoFiles.length; i++) {
    formData.append('muzzle_photos', muzzlePhotoFiles[i]);
}

fetch('http://127.0.0.1:8000/api/register/', {
    method: 'POST',
    body: formData
})
.then(response => response.json())
.then(data => {
    console.log('Registration successful!');
    console.log('Training status ID:', data.training.training_status_id);
    // Use training_status_id to check training progress
})
.catch(error => console.error('Error:', error));
```

## Response Format

### Success Response (201 Created)

```json
{
    "message": "Cow registered successfully. Training started in background.",
    "cow_profile": {
        "id": 1,
        "policy_id": "POL-20260110-145030-A1B2C3D4",
        "cow_name": "Bella",
        "cow_age": 24,
        "cow_breed": "Holstein",
        "owner_name": "John Doe",
        "cow_id": "COW-20260110-145030-E5F6G7H8",
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z"
    },
    "user": {
        "id": 1,
        "username": "user_bella_A1B2C3D4",
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "date_joined": "2024-01-01T12:00:00Z"
    },
    "photos": {
        "cow_photos_saved": 2,
        "muzzle_photos_saved": 3,
        "cow_photos_directory": "media/cow_images/POL-20260110-145030-A1B2C3D4/cow_photos",
        "muzzle_photos_directory": "media/cow_images/POL-20260110-145030-A1B2C3D4/muzzle_photos"
    },
    "training": {
        "status": "started",
        "message": "Training started in background",
        "training_status_id": 1,
        "check_status_url": "/api/training-status/1/"
    },
    "is_new_registration": true
}
```

### Error Response (400 Bad Request)

```json
{
    "muzzle_photos": ["At least one muzzle photo is required for training."],
    "cow_name": ["This field is required."]
}
```

## Check Training Status

**GET** `/api/training-status/{training_id}/`

After registration, use the `training_status_id` from the response to check training progress.

### Response Examples

#### Training in Progress
```json
{
    "id": 1,
    "status": "running",
    "started_at": "2024-01-01T12:00:00Z",
    "completed_at": null,
    "error_message": "",
    "num_images": null,
    "epochs": null,
    "checkpoint_path": ""
}
```

#### Training Completed
```json
{
    "id": 1,
    "status": "completed",
    "started_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:05:30Z",
    "error_message": "",
    "num_images": 3,
    "epochs": 50,
    "checkpoint_path": "/path/to/cae_checkpoint.pt"
}
```

#### Training Failed
```json
{
    "id": 1,
    "status": "failed",
    "started_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:02:15Z",
    "error_message": "Error message here",
    "num_images": null,
    "epochs": null,
    "checkpoint_path": ""
}
```

### Training Status Values

- `pending`: Training is queued but not started yet
- `running`: Training is currently in progress
- `completed`: Training finished successfully
- `failed`: Training encountered an error

### Polling Example (Python)

```python
import requests
import time

# Register cow
response = requests.post('http://127.0.0.1:8000/api/register/', ...)
data = response.json()
training_id = data['training']['training_status_id']

# Poll for status
while True:
    status_response = requests.get(f'http://127.0.0.1:8000/api/training-status/{training_id}/')
    status_data = status_response.json()
    
    if status_data['status'] == 'completed':
        print("Training completed!")
        print(f"Images: {status_data['num_images']}")
        print(f"Epochs: {status_data['epochs']}")
        break
    elif status_data['status'] == 'failed':
        print(f"Training failed: {status_data['error_message']}")
        break
    else:
        print(f"Training status: {status_data['status']}")
        time.sleep(5)  # Wait 5 seconds before checking again
```

## Important Notes

### ID Generation

- **`policy_id` is automatically generated** server-side when you register a cow
  - Format: `POL-{YYYYMMDD}-{HHMMSS}-{8-char-UUID}` (e.g., `POL-20260110-145030-A1B2C3D4`)
  - The generated `policy_id` is returned in the response and should be saved by the client for future reference
  - The same `policy_id` and `cow_name` combination cannot be registered twice (unique constraint)

- **`cow_id` is automatically generated** server-side when you register a cow
  - Format: `COW-{YYYYMMDD}-{HHMMSS}-{8-char-UUID}` (e.g., `COW-20260110-145030-E5F6G7H8`)
  - The generated `cow_id` is unique across all cow profiles
  - The generated `cow_id` is returned in the response

### Photo Handling

1. **Cow Photos**: Saved to `media/cow_images/{policy_id}/cow_photos/`
   - These are stored but **NOT used for training**
   - Useful for reference/documentation

2. **Muzzle Photos**: Saved to `media/cow_images/{policy_id}/muzzle_photos/`
   - These are **USED for ML training**
   - At least one required if `train_model=true`

### Training Process (Asynchronous)

- Model trains **ONLY using muzzle photos**
- Training happens **asynchronously in background** (API returns immediately)
- API response includes `training_status_id` to check training progress
- Use `/api/training-status/{training_status_id}/` to check training status
- Model checkpoint is updated incrementally when training completes
- Embedding plots are generated after training completes

### Data Storage

All information is saved to the database:
- Policy ID (automatically generated, unique per cow_name combination)
- Cow ID (automatically generated, unique across all profiles)
- Cow name, age, breed
- Owner name
- User information
- Photo locations

### File Structure

After registration, files are organized as:

```
media/
  cow_images/
    POL-20260110-145030-A1B2C3D4/
      cow_photos/
        Bella_cow_1.jpg
        Bella_cow_2.jpg
      muzzle_photos/
        Bella_muzzle_1.jpg
        Bella_muzzle_2.jpg
        Bella_muzzle_3.jpg
```

## Validation Rules

- `cow_name`: Required
- `policy_id`: Automatically generated server-side (format: `POL-YYYYMMDD-HHMMSS-{UUID}`)
- `cow_id`: Automatically generated server-side (format: `COW-YYYYMMDD-HHMMSS-{UUID}`)
- `muzzle_photos`: Required if `train_model=true` (at least 1 photo)
- `password`: If provided, must match `password_confirm` and be at least 8 characters

## Training Parameters

Default training parameters:
- `epochs`: 50
- `batch_size`: 8
- `contrastive_weight`: 0.8
- `learning_rate`: 5e-4 (fixed)
- `image_size`: 224 (fixed)
- `latent_dim`: 128 (fixed)

These can be customized per request.

## Benefits of Asynchronous Training

1. **Fast Response**: API returns immediately (usually < 1 second)
2. **No Timeout**: Training can take as long as needed
3. **Better UX**: Users don't wait for training
4. **Status Tracking**: Can check progress anytime
5. **Error Handling**: Failed training doesn't block registration

## Notes

- Training runs in a background thread (daemon thread)
- If the server restarts, pending/running training will be lost
- For production, consider using Celery or similar task queue
- Training status is stored in database and persists across requests
- Multiple cows can be registered simultaneously (each has its own training thread)
- If a cow with the same `policy_id` and `cow_name` already exists, the existing record will be updated
