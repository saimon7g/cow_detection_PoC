"""
Service module to handle incremental ML training from API calls.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Optional

# Set matplotlib to use non-GUI backend (required for server environments)
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend - must be set before importing pyplot

# Add parent directory to path to import ML modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def train_cow_incremental(
    cow_images_dir: Path,
    cow_name: str,
    checkpoint_path: Optional[Path] = None,
    epochs: int = 50,
    batch_size: int = 8,
    contrastive_weight: float = 0.8,
    lr: float = 5e-4,
    image_size: int = 224,
    latent_dim: int = 128,
) -> Dict:
    """
    Run incremental training for a cow.
    
    Args:
        cow_images_dir: Directory containing cow images
        cow_name: Name of the cow
        checkpoint_path: Path to checkpoint file (default: PROJECT_ROOT/cae_checkpoint.pt)
        epochs: Number of training epochs
        batch_size: Batch size for training
        contrastive_weight: Weight for contrastive loss
        lr: Learning rate
        image_size: Image size for training
        latent_dim: Latent dimension
    
    Returns:
        Dictionary with training results and metrics
    """
    if checkpoint_path is None:
        checkpoint_path = PROJECT_ROOT / "cae_checkpoint.pt"
    
    metrics_file = PROJECT_ROOT / "training_metrics.json"
    plot_dir = PROJECT_ROOT / "plots"
    
    # Import here to avoid circular imports
    from incremental_train import (
        load_checkpoint,
        save_checkpoint,
        train_incremental,
        extract_embeddings,
        plot_all_embeddings,
        plot_class_means,
        build_transforms,
        SingleCowDataset,
        ConvAutoencoder,
        save_metrics,
    )
    from torch.utils.data import DataLoader
    import torch
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Load existing checkpoint or create new model
    model, class_to_idx, class_means, checkpoint_latent_dim, checkpoint_image_size = load_checkpoint(checkpoint_path, device)
    
    # Use checkpoint values if available, otherwise use function parameters
    if checkpoint_latent_dim is not None:
        latent_dim = checkpoint_latent_dim
    if checkpoint_image_size is not None:
        image_size = checkpoint_image_size
    
    if model is None:
        model = ConvAutoencoder(latent_dim=latent_dim, image_size=image_size).to(device)
        class_to_idx = {}
        class_means = {}
    
    # Check if cow already exists
    if cow_name in class_to_idx:
        cow_id = class_to_idx[cow_name]
    else:
        cow_id = len(class_to_idx)
        class_to_idx[cow_name] = cow_id
    
    # Create dataset and dataloader
    transform = build_transforms(image_size)
    dataset = SingleCowDataset(cow_images_dir, transform, cow_id)
    pin_mem = device.type == "cuda"
    train_loader = DataLoader(
        dataset, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=pin_mem
    )
    
    # Train
    metrics = train_incremental(
        model=model,
        train_loader=train_loader,
        device=device,
        epochs=epochs,
        lr=lr,
        contrastive_weight=contrastive_weight,
        cow_name=cow_name,
    )
    
    # Extract embeddings and compute class mean
    train_embs, train_labels = extract_embeddings(model, train_loader, device)
    
    # Update class mean
    cow_embeddings = train_embs[train_labels == cow_id]
    if len(cow_embeddings) > 0:
        class_means[cow_id] = cow_embeddings.mean(dim=0).to(device)
        metrics["embedding_mean_norm"] = float(torch.norm(class_means[cow_id]).item())
        metrics["num_images"] = len(cow_embeddings)
    
    # Save checkpoint
    save_checkpoint(
        model=model,
        class_to_idx=class_to_idx,
        class_means=class_means,
        latent_dim=latent_dim,
        image_size=image_size,
        checkpoint_path=checkpoint_path,
    )
    
    # Save metrics
    save_metrics(metrics, metrics_file)
    
    # Create plots directory
    plot_dir.mkdir(exist_ok=True)
    
    # Plot embeddings
    all_embeddings_plot_path = plot_dir / "all_embeddings.png"
    class_means_plot_path = plot_dir / "class_means.png"
    
    plot_all_embeddings(
        model,
        class_to_idx,
        class_means,
        device,
        all_embeddings_plot_path,
        current_cow_loader=train_loader,
        current_cow_id=cow_id,
        current_cow_name=cow_name,
    )
    
    plot_class_means(
        class_to_idx,
        class_means,
        class_means_plot_path,
    )
    
    return {
        "success": True,
        "cow_name": cow_name,
        "cow_id": cow_id,
        "num_images": len(cow_embeddings),
        "epochs": epochs,
        "metrics": metrics,
        "checkpoint_path": str(checkpoint_path),
    }

