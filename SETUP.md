# Setup and Run Guide

Complete guide to set up and run the Cow Detection PoC project.

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

## Step 1: Navigate to Project Directory

```bash
cd /Users/saimon/Documents/Github/cow_detection_PoC
```

## Step 2: Create Virtual Environment

If you haven't already created a virtual environment:

```bash
python3 -m venv venv
```

## Step 3: Activate Virtual Environment

**On macOS/Linux:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

## Step 4: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install:
- Django & Django REST Framework
- django-cors-headers
- PyTorch & torchvision
- matplotlib
- scikit-learn

## Step 5: Set Up Django Backend

### 5.1 Navigate to Backend Directory

```bash
cd cow_detection_backend
```

### 5.2 Create Database Migrations

This creates migration files for the database schema:

```bash
python manage.py makemigrations
```

### 5.3 Apply Database Migrations

This creates the database tables:

```bash
python manage.py migrate
```

### 5.4 Create Superuser (Optional)

For accessing the Django admin panel:

```bash
python manage.py createsuperuser
```

Follow the prompts to create an admin user.

### 5.5 Run the Development Server

```bash
python manage.py runserver
```

The server will start at `http://127.0.0.1:8000/`

## Step 6: Test the API

### Quick Test

```bash
curl -X POST http://127.0.0.1:8000/api/register/ \
  -F "policy_id=POL-2024-001" \
  -F "cow_name=TestCow" \
  -F "muzzle_photos=@/path/to/your/muzzle_photo.jpg" \
  -F "train_model=true"
```

## Quick Start (All Commands at Once)

```bash
# Navigate to project
cd /Users/saimon/Documents/Github/cow_detection_PoC

# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Navigate to backend
cd cow_detection_backend

# Setup database
python manage.py makemigrations
python manage.py migrate

# Start server
python manage.py runserver
```

## Access Points

Once the server is running:

- **API Endpoint**: `http://127.0.0.1:8000/api/register/`
- **Training Status**: `http://127.0.0.1:8000/api/training-status/{id}/`
- **Admin Panel**: `http://127.0.0.1:8000/admin/` (requires superuser)
- **API Documentation**: See `cow_detection_backend/API_DOCUMENTATION.md`

## Troubleshooting

### Port Already in Use

If port 8000 is busy, use a different port:

```bash
python manage.py runserver 8001
```

Or kill the process using port 8000:

```bash
kill -9 $(lsof -ti:8000)
```

### Database Errors

If you get database errors, try:

```bash
cd cow_detection_backend
python manage.py makemigrations
python manage.py migrate
```

### Module Not Found Errors

Make sure virtual environment is activated:

```bash
source venv/bin/activate  # macOS/Linux
```

Check if Django is installed:

```bash
pip list | grep -i django
```

If not installed:

```bash
pip install -r requirements.txt
```

### Permission Errors

On macOS/Linux, if you get permission errors:

```bash
chmod +x venv/bin/activate
```

## Project Structure

```
cow_detection_PoC/
├── venv/                    # Virtual environment
├── cow_detection_backend/   # Django backend
│   ├── manage.py
│   ├── db.sqlite3          # Database (created after migrate)
│   ├── media/              # Uploaded images (created automatically)
│   │   └── cow_images/
│   ├── cow_detection_backend/
│   └── api/
├── incremental_train.py     # ML training script (standalone)
├── contrastive_autoencoder.py  # ML model definition
├── cae_checkpoint.pt       # ML model checkpoint
├── training_metrics.json   # Training metrics
├── plots/                  # Embedding visualizations
├── requirements.txt        # Python dependencies
├── README.md              # Project overview
└── SETUP.md               # This file
```

## Next Steps

1. Test the registration API with sample data
2. Check the admin panel to see registered cows
3. Verify photos are saved in `media/cow_images/`
4. Check training results in `cae_checkpoint.pt` and `plots/`
5. See `cow_detection_backend/API_DOCUMENTATION.md` for complete API documentation
