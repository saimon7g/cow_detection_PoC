"""
Service module to handle cow image classification using the trained model.
"""
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import tempfile

# Set matplotlib to use non-GUI backend (required for server environments)
import matplotlib
matplotlib.use('Agg')

# Add parent directory to path to import ML modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import torch
from PIL import Image
from contrastive_autoencoder import ConvAutoencoder, build_transforms


def load_model_and_centroids(
    checkpoint_path: Optional[Path] = None
) -> Tuple[ConvAutoencoder, Dict, Dict, int, torch.device]:
    """
    Load the trained model and class centroids from checkpoint.
    
    Args:
        checkpoint_path: Path to checkpoint file (default: PROJECT_ROOT/cae_checkpoint.pt)
    
    Returns:
        Tuple of (model, class_means, idx_to_class, image_size, device)
    """
    if checkpoint_path is None:
        checkpoint_path = PROJECT_ROOT / "cae_checkpoint.pt"
    
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found at {checkpoint_path}")
    
    ckpt = torch.load(checkpoint_path, map_location="cpu")
    latent_dim = ckpt["latent_dim"]
    image_size = ckpt["image_size"]
    class_to_idx = ckpt["class_to_idx"]
    idx_to_class = {v: k for k, v in class_to_idx.items()}
    class_means = {int(k): v for k, v in ckpt["class_means"].items()}
    
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    model = ConvAutoencoder(latent_dim=latent_dim, image_size=image_size)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()
    
    return model, class_means, idx_to_class, image_size, device


@torch.no_grad()
def classify_cow_image(
    image_file,
    checkpoint_path: Optional[Path] = None,
    top_k: int = 5,
    threshold: Optional[float] = None
) -> List[Dict]:
    """
    Classify a cow image and return top-K matching profiles.
    
    Args:
        image_file: Django uploaded file or file path
        checkpoint_path: Path to checkpoint file (default: PROJECT_ROOT/cae_checkpoint.pt)
        top_k: Number of top matches to return
        threshold: Optional distance threshold - only return matches below this threshold
    
    Returns:
        List of dictionaries with 'cow_name', 'distance', 'rank' for each match
    """
    # Load model and centroids
    model, class_means, idx_to_class, image_size, device = load_model_and_centroids(checkpoint_path)
    transform = build_transforms(image_size)
    
    # Handle file input (Django UploadedFile or Path)
    if hasattr(image_file, 'read'):
        # Django UploadedFile - save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            for chunk in image_file.chunks():
                tmp_file.write(chunk)
            tmp_file_path = tmp_file.name
        try:
            img = Image.open(tmp_file_path).convert("RGB")
        finally:
            os.unlink(tmp_file_path)
    else:
        # Path object
        img = Image.open(image_file).convert("RGB")
    
    # Transform and get embedding
    tensor = transform(img).unsqueeze(0).to(device)
    _, embedding = model(tensor)
    embedding = embedding.cpu()
    
    # Calculate distances to all class centroids
    distances = []
    for cls_idx, centroid in class_means.items():
        dist = torch.norm(embedding - centroid, dim=1).item()
        cow_name = idx_to_class[cls_idx]
        distances.append({
            'cow_name': cow_name,
            'distance': float(dist),
            'class_idx': int(cls_idx)
        })
    
    # Sort by distance
    distances.sort(key=lambda x: x['distance'])
    
    # Apply threshold if provided
    if threshold is not None:
        distances = [d for d in distances if d['distance'] <= threshold]
    
    # Get top-K
    top_k = min(top_k, len(distances))
    results = distances[:top_k]
    
    # Add rank
    for rank, result in enumerate(results, start=1):
        result['rank'] = rank
    
    return results

