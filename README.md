# Cow Detection PoC

A proof-of-concept system for cow detection and identification using contrastive autoencoder with incremental learning.

## Features

- **Incremental ML Training**: Train the model on one cow at a time, learning incrementally
- **REST API**: Django backend with single API call for cow registration
- **Asynchronous Training**: Training runs in background, API returns immediately
- **Muzzle Photo Recognition**: Model trains using only muzzle photos for identification
- **Embedding Visualization**: Automatic generation of t-SNE plots showing cow clusters
- **Complete Data Management**: Store policy info, cow details, owner info, and photos

## Quick Start

### 1. Setup Environment

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Django Backend

```bash
cd cow_detection_backend
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

API will be available at `http://127.0.0.1:8000/api/`

### 3. Register a Cow

```bash
curl -X POST http://127.0.0.1:8000/api/register/ \
  -F "policy_id=POL-2024-001" \
  -F "cow_name=Bella" \
  -F "muzzle_photos=@/path/to/muzzle_photo.jpg" \
  -F "train_model=true"
```

## Documentation

- **[SETUP.md](SETUP.md)** - Complete setup and installation guide
- **[cow_detection_backend/API_DOCUMENTATION.md](cow_detection_backend/API_DOCUMENTATION.md)** - Complete API documentation with examples

## How It Works

### Incremental Training

The model learns incrementally - you can train on one cow at a time:

```bash
# Train first cow
python3 incremental_train.py \
  --cow-images path/to/cow_a_images/ \
  --cow-name sapi_a \
  --epochs 50

# Train additional cows (loads previous checkpoint)
python3 incremental_train.py \
  --cow-images path/to/cow_b_images/ \
  --cow-name sapi_b \
  --epochs 50
```

### API Registration

Register cows via API with automatic training:

1. Send cow information + photos via API
2. API validates and saves data immediately
3. Training starts in background
4. Check training status via status endpoint

## Key Components

- **ML Model**: Contrastive autoencoder for cow identification
- **Django API**: REST API for cow registration
- **Incremental Learning**: Add new cows without retraining from scratch
- **Background Training**: Non-blocking ML training
- **Status Tracking**: Monitor training progress

## Output Files

- `cae_checkpoint.pt`: Model checkpoint (updated after each cow)
- `training_metrics.json`: Training metrics for all cows
- `plots/all_embeddings.png`: All embedding points visualization
- `plots/class_means.png`: Class means visualization
- `cow_detection_backend/media/`: Uploaded cow and muzzle photos

## Project Structure

```
cow_detection_PoC/
├── cow_detection_backend/   # Django API backend
│   ├── api/                 # API endpoints
│   ├── media/               # Uploaded images
│   └── API_DOCUMENTATION.md # API docs
├── incremental_train.py     # Standalone training script
├── contrastive_autoencoder.py  # ML model
├── requirements.txt         # Dependencies
├── README.md               # This file
└── SETUP.md                # Setup guide
```

## License

See LICENSE file for details.
