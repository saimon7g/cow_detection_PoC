"""
Incremental training script for contrastive autoencoder.
Train on a single cow at a time, save metrics, and update the model incrementally.

Example:
    # First cow
    python incremental_train.py --cow-images path/to/cow_a_images/ --cow-name sapi_a --epochs 50
    
    # Second cow (will load previous checkpoint)
    python incremental_train.py --cow-images path/to/cow_b_images/ --cow-name sapi_b --epochs 50
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

# Set matplotlib to use non-GUI backend (required for server environments)
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from sklearn.manifold import TSNE
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms

from contrastive_autoencoder import (
    ConvAutoencoder,
    build_transforms,
    supervised_contrastive_loss,
)


class SingleCowDataset(Dataset):
    """Dataset for a single cow with multiple images."""
    
    def __init__(self, image_dir: Path, transform, cow_id: int):
        self.image_dir = Path(image_dir)
        self.transform = transform
        self.cow_id = cow_id
        
        # Find all image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        self.image_paths = [
            p for p in self.image_dir.iterdir() 
            if p.suffix.lower() in image_extensions and p.is_file()
        ]
        
        if len(self.image_paths) == 0:
            raise ValueError(f"No images found in {image_dir}")
        
        print(f"Found {len(self.image_paths)} images for cow_id {cow_id}")
    
    def __len__(self):
        return len(self.image_paths)
    
    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        img = Image.open(img_path).convert('RGB')
        img_tensor = self.transform(img)
        return img_tensor, self.cow_id


def load_checkpoint(checkpoint_path: Path, device: torch.device) -> Tuple[ConvAutoencoder, Dict, Dict, int, int]:
    """Load existing checkpoint or return None if it doesn't exist."""
    if not checkpoint_path.exists():
        return None, {}, {}, None, None
    
    ckpt = torch.load(checkpoint_path, map_location=device)
    latent_dim = ckpt["latent_dim"]
    image_size = ckpt["image_size"]
    class_to_idx = ckpt["class_to_idx"]
    class_means = {int(k): v.to(device) if isinstance(v, torch.Tensor) else v for k, v in ckpt["class_means"].items()}
    
    model = ConvAutoencoder(latent_dim=latent_dim, image_size=image_size)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    
    return model, class_to_idx, class_means, latent_dim, image_size


def save_checkpoint(
    model: ConvAutoencoder,
    class_to_idx: Dict,
    class_means: Dict,
    latent_dim: int,
    image_size: int,
    checkpoint_path: Path,
) -> None:
    """Save model checkpoint with updated class information."""
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "class_to_idx": class_to_idx,
            "class_means": {k: v.cpu() if isinstance(v, torch.Tensor) else v for k, v in class_means.items()},
            "latent_dim": latent_dim,
            "image_size": image_size,
        },
        checkpoint_path,
    )
    print(f"Saved checkpoint to {checkpoint_path}")


def train_incremental(
    model: ConvAutoencoder,
    train_loader: DataLoader,
    device: torch.device,
    epochs: int,
    lr: float,
    contrastive_weight: float,
    cow_name: str,
) -> Dict:
    """Train model incrementally on new cow data and return metrics."""
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    
    metrics = {
        "cow_name": cow_name,
        "epochs": epochs,
        "epoch_metrics": []
    }
    
    for epoch in range(1, epochs + 1):
        model.train()
        running_recon, running_contrast = 0.0, 0.0
        total_samples = 0
        
        for imgs, labels in train_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            opt.zero_grad()
            recon, z = model(imgs)
            recon_loss = F.mse_loss(recon, imgs)
            con_loss = supervised_contrastive_loss(z, labels)
            loss = recon_loss + contrastive_weight * con_loss
            loss.backward()
            opt.step()
            
            batch_size = imgs.size(0)
            running_recon += recon_loss.item() * batch_size
            running_contrast += con_loss.item() * batch_size
            total_samples += batch_size
        
        avg_recon = running_recon / total_samples if total_samples > 0 else 0.0
        avg_contrast = running_contrast / total_samples if total_samples > 0 else 0.0
        
        epoch_metric = {
            "epoch": epoch,
            "reconstruction_loss": float(avg_recon),
            "contrastive_loss": float(avg_contrast),
            "total_loss": float(avg_recon + contrastive_weight * avg_contrast)
        }
        metrics["epoch_metrics"].append(epoch_metric)
        
        print(
            f"[{cow_name}] Epoch {epoch:02d}/{epochs} | "
            f"recon {avg_recon:.4f} | contrast {avg_contrast:.4f}"
        )
    
    return metrics


@torch.no_grad()
def extract_embeddings(model: ConvAutoencoder, loader: DataLoader, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
    """Extract embeddings from the model."""
    model.eval()
    embs, labels_all = [], []
    for imgs, labels in loader:
        imgs = imgs.to(device)
        z = model.encode(imgs)
        embs.append(z.cpu())
        labels_all.append(labels.cpu())
    return torch.cat(embs), torch.cat(labels_all)


def save_metrics(metrics: Dict, metrics_path: Path):
    """Save training metrics to JSON file, appending if file exists."""
    if metrics_path.exists():
        with open(metrics_path, 'r') as f:
            all_metrics = json.load(f)
    else:
        all_metrics = {"training_sessions": []}
    
    all_metrics["training_sessions"].append(metrics)
    
    with open(metrics_path, 'w') as f:
        json.dump(all_metrics, f, indent=2)
    
    print(f"Saved metrics to {metrics_path}")


def plot_training_curves(metrics: Dict, plot_path: Path, cow_name: str):
    """Plot training loss curves for the current training session."""
    epochs = [m["epoch"] for m in metrics["epoch_metrics"]]
    recon_losses = [m["reconstruction_loss"] for m in metrics["epoch_metrics"]]
    contrast_losses = [m["contrastive_loss"] for m in metrics["epoch_metrics"]]
    total_losses = [m["total_loss"] for m in metrics["epoch_metrics"]]
    
    plt.figure(figsize=(12, 5))
    
    # Plot 1: All losses together
    plt.subplot(1, 2, 1)
    plt.plot(epochs, recon_losses, label='Reconstruction Loss', marker='o', markersize=3)
    plt.plot(epochs, contrast_losses, label='Contrastive Loss', marker='s', markersize=3)
    plt.plot(epochs, total_losses, label='Total Loss', marker='^', markersize=3)
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title(f'Training Losses - {cow_name}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot 2: Loss reduction over time
    plt.subplot(1, 2, 2)
    plt.plot(epochs, recon_losses, label='Reconstruction', marker='o', markersize=3, alpha=0.7)
    plt.plot(epochs, total_losses, label='Total', marker='^', markersize=3, alpha=0.7)
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title(f'Loss Reduction - {cow_name}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved training plot to {plot_path}")


def plot_all_embeddings(
    model: ConvAutoencoder,
    class_to_idx: Dict,
    class_means: Dict,
    device: torch.device,
    plot_path: Path,
    current_cow_loader: DataLoader = None,
    current_cow_id: int = None,
    current_cow_name: str = None,
):
    """Plot t-SNE visualization of ALL individual embedding points from all cows."""
    # Collect all individual embeddings from all cows
    all_embeddings = []
    all_labels = []
    all_class_names = []
    
    # For each cow, we need to extract individual embeddings
    # For now, we'll use the current cow's loader and store means for others
    # In a full implementation, you'd load all cow data, but for incremental training
    # we only have access to the current cow's images
    
    # Add current cow's individual embeddings
    if current_cow_loader is not None and current_cow_id is not None:
        model.eval()
        current_embs = []
        with torch.no_grad():
            for imgs, labels in current_cow_loader:
                imgs = imgs.to(device)
                z = model.encode(imgs)
                current_embs.append(z.cpu())
        
        if len(current_embs) > 0:
            current_embs_tensor = torch.cat(current_embs)
            cow_name = current_cow_name if current_cow_name else list(class_to_idx.keys())[list(class_to_idx.values()).index(current_cow_id)]
            for emb in current_embs_tensor:
                all_embeddings.append(emb)
                all_labels.append(current_cow_id)
                all_class_names.append(cow_name)
    
    # For other cows, we can't get individual embeddings without their data
    # So we'll use their class means as single points (they'll appear as one point per cow)
    for cow_name, cow_id in class_to_idx.items():
        if cow_id != current_cow_id and cow_id in class_means:
            mean_emb = class_means[cow_id]
            if isinstance(mean_emb, torch.Tensor):
                all_embeddings.append(mean_emb.cpu())
            else:
                all_embeddings.append(torch.tensor(mean_emb))
            all_labels.append(cow_id)
            all_class_names.append(cow_name)
    
    if len(all_embeddings) == 0:
        print("No embeddings to plot")
        return
    
    embeddings_array = torch.stack(all_embeddings).numpy()
    labels_array = torch.tensor(all_labels).numpy()
    
    # Apply t-SNE - perplexity must be less than n_samples
    n_samples = len(embeddings_array)
    
    # Special case: if only 1 sample, can't use t-SNE (perplexity must be < n_samples)
    if n_samples == 1:
        # Just plot a single point
        unique_labels = torch.unique(torch.tensor(all_labels)).numpy()
        plt.figure(figsize=(10, 8))
        plt.scatter([0], [0], s=300, alpha=0.7, c='blue', edgecolors='black', linewidths=2)
        plt.annotate(
            all_class_names[0],
            (0, 0),
            fontsize=12,
            ha='center',
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8)
        )
        plt.title(f'All Embedding Points - {len(unique_labels)} cow', fontsize=14, fontweight='bold')
        plt.xlabel('Embedding Dimension 1', fontsize=12)
        plt.ylabel('Embedding Dimension 2', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Saved all embeddings plot to {plot_path} (single point)")
        return
    
    # Calculate perplexity: must be strictly less than n_samples
    # Use min(30, max(5, n_samples - 1)) but ensure it's < n_samples
    perplexity = min(30, max(5, n_samples - 1))
    # Ensure perplexity is strictly less than n_samples
    if perplexity >= n_samples:
        perplexity = n_samples - 1
    # Final safety check
    if perplexity < 1:
        perplexity = 1
    tsne = TSNE(n_components=2, init="pca", learning_rate="auto", perplexity=perplexity, random_state=42)
    reduced = tsne.fit_transform(embeddings_array)
    
    # Plot
    plt.figure(figsize=(14, 10))
    
    # Get unique labels and colors
    unique_labels = torch.unique(torch.tensor(all_labels)).numpy()
    colors = plt.cm.tab20(range(len(unique_labels)))
    label_to_color = {label: colors[i % len(colors)] for i, label in enumerate(unique_labels)}
    
    # Plot each cow's embeddings
    for label in unique_labels:
        mask = labels_array == label
        cow_name = [name for name, lid in zip(all_class_names, all_labels) if lid == label][0]
        point_size = 100 if mask.sum() == 1 else 50  # Larger if it's just one point (mean)
        plt.scatter(
            reduced[mask, 0], 
            reduced[mask, 1], 
            s=point_size,
            alpha=0.7, 
            c=[label_to_color[label]], 
            label=cow_name,
            edgecolors='black',
            linewidths=1
        )
    
    # Add labels
    seen_labels = set()
    for i, (label, name) in enumerate(zip(all_labels, all_class_names)):
        if label not in seen_labels:
            plt.annotate(
                name, 
                (reduced[i, 0], reduced[i, 1]), 
                fontsize=10, 
                ha='center',
                fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7)
            )
            seen_labels.add(label)
    
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.title(f'All Embedding Points (t-SNE) - {len(unique_labels)} cows', fontsize=14, fontweight='bold')
    plt.xlabel('t-SNE Component 1', fontsize=12)
    plt.ylabel('t-SNE Component 2', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved all embeddings plot to {plot_path}")


def plot_class_means(
    class_to_idx: Dict,
    class_means: Dict,
    plot_path: Path,
):
    """Plot t-SNE visualization of ONLY class means (one point per cow)."""
    # Collect only class means
    mean_embeddings = []
    mean_labels = []
    mean_class_names = []
    
    for cow_name, cow_id in class_to_idx.items():
        if cow_id in class_means:
            mean_emb = class_means[cow_id]
            if isinstance(mean_emb, torch.Tensor):
                mean_embeddings.append(mean_emb.cpu())
            else:
                mean_embeddings.append(torch.tensor(mean_emb))
            mean_labels.append(cow_id)
            mean_class_names.append(cow_name)
    
    if len(mean_embeddings) == 0:
        print("No class means to plot")
        return
    
    if len(mean_embeddings) == 1:
        # Special case: only one cow, just plot it
        plt.figure(figsize=(10, 8))
        plt.scatter([0], [0], s=300, alpha=0.7, c='blue', edgecolors='black', linewidths=2)
        plt.annotate(
            mean_class_names[0],
            (0, 0),
            fontsize=12,
            ha='center',
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8)
        )
        plt.title(f'Class Means - {len(mean_class_names)} cow', fontsize=14, fontweight='bold')
        plt.xlabel('Embedding Dimension 1', fontsize=12)
        plt.ylabel('Embedding Dimension 2', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Saved class means plot to {plot_path}")
        return
    
    embeddings_array = torch.stack(mean_embeddings).numpy()
    labels_array = torch.tensor(mean_labels).numpy()
    
    # Apply t-SNE - perplexity must be less than n_samples
    n_samples = len(embeddings_array)
    
    # Calculate perplexity: must be strictly less than n_samples
    # Use min(30, max(5, n_samples - 1)) but ensure it's < n_samples
    perplexity = min(30, max(5, n_samples - 1))
    # Ensure perplexity is strictly less than n_samples
    if perplexity >= n_samples:
        perplexity = n_samples - 1
    # Final safety check
    if perplexity < 1:
        perplexity = 1
    
    tsne = TSNE(n_components=2, init="pca", learning_rate="auto", perplexity=perplexity, random_state=42)
    reduced = tsne.fit_transform(embeddings_array)
    
    # Plot
    plt.figure(figsize=(14, 10))
    
    # Get unique labels and colors
    unique_labels = torch.unique(torch.tensor(mean_labels)).numpy()
    colors = plt.cm.tab20(range(len(unique_labels)))
    label_to_color = {label: colors[i % len(colors)] for i, label in enumerate(unique_labels)}
    
    # Plot each cow's mean
    for label in unique_labels:
        mask = labels_array == label
        cow_name = mean_class_names[list(mean_labels).index(label)]
        plt.scatter(
            reduced[mask, 0], 
            reduced[mask, 1], 
            s=300,
            alpha=0.8, 
            c=[label_to_color[label]], 
            label=cow_name,
            edgecolors='black',
            linewidths=2
        )
    
    # Add labels
    for i, (label, name) in enumerate(zip(mean_labels, mean_class_names)):
        plt.annotate(
            name, 
            (reduced[i, 0], reduced[i, 1]), 
            fontsize=12, 
            ha='center',
            fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.8)
        )
    
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
    plt.title(f'Class Means (t-SNE) - {len(unique_labels)} cows', fontsize=14, fontweight='bold')
    plt.xlabel('t-SNE Component 1', fontsize=12)
    plt.ylabel('t-SNE Component 2', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved class means plot to {plot_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Incremental training for contrastive autoencoder - train one cow at a time."
    )
    parser.add_argument(
        "--cow-images",
        type=Path,
        required=True,
        help="Directory containing images of a single cow (5-10 images recommended).",
    )
    parser.add_argument(
        "--cow-name",
        type=str,
        required=True,
        help="Name/ID of the cow (e.g., 'sapi_a', 'cow_001').",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("cae_checkpoint.pt"),
        help="Path to checkpoint file (will load if exists, create new if not).",
    )
    parser.add_argument(
        "--metrics-file",
        type=Path,
        default=Path("training_metrics.json"),
        help="Path to JSON file storing training metrics.",
    )
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs for this cow.")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size.")
    parser.add_argument("--lr", type=float, default=5e-4, help="Learning rate.")
    parser.add_argument("--latent-dim", type=int, default=128, help="Size of latent vector.")
    parser.add_argument("--contrastive-weight", type=float, default=0.8, help="Weight for contrastive loss.")
    parser.add_argument("--image-size", type=int, default=224, help="Square resize for images.")
    parser.add_argument(
        "--plot-dir",
        type=Path,
        default=Path("plots"),
        help="Directory to save training plots.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Load existing checkpoint or create new model
    model, class_to_idx, class_means, latent_dim, image_size = load_checkpoint(args.checkpoint, device)
    
    if model is None:
        print("No existing checkpoint found. Creating new model...")
        latent_dim = args.latent_dim
        image_size = args.image_size
        model = ConvAutoencoder(latent_dim=latent_dim, image_size=image_size).to(device)
        class_to_idx = {}
        class_means = {}
    else:
        print(f"Loaded checkpoint with {len(class_to_idx)} existing cows: {list(class_to_idx.keys())}")
        # Use checkpoint's image_size and latent_dim
        args.image_size = image_size
        args.latent_dim = latent_dim
    
    # Check if cow already exists
    if args.cow_name in class_to_idx:
        cow_id = class_to_idx[args.cow_name]
        print(f"Cow '{args.cow_name}' already exists with ID {cow_id}. Updating with new images...")
    else:
        # Assign new ID
        cow_id = len(class_to_idx)
        class_to_idx[args.cow_name] = cow_id
        print(f"Adding new cow '{args.cow_name}' with ID {cow_id}")
    
    # Create dataset and dataloader for this cow
    transform = build_transforms(args.image_size)
    dataset = SingleCowDataset(args.cow_images, transform, cow_id)
    pin_mem = device.type == "cuda"
    train_loader = DataLoader(
        dataset, batch_size=args.batch_size, shuffle=True, num_workers=2, pin_memory=pin_mem
    )
    
    # Train on this cow
    print(f"\nTraining on cow '{args.cow_name}' with {len(dataset)} images...")
    metrics = train_incremental(
        model=model,
        train_loader=train_loader,
        device=device,
        epochs=args.epochs,
        lr=args.lr,
        contrastive_weight=args.contrastive_weight,
        cow_name=args.cow_name,
    )
    
    # Extract embeddings and compute class mean
    print(f"\nExtracting embeddings for cow '{args.cow_name}'...")
    train_embs, train_labels = extract_embeddings(model, train_loader, device)
    
    # Update class mean (average of all embeddings for this cow)
    cow_embeddings = train_embs[train_labels == cow_id]
    if len(cow_embeddings) > 0:
        class_means[cow_id] = cow_embeddings.mean(dim=0).to(device)
        metrics["embedding_mean_norm"] = float(torch.norm(class_means[cow_id]).item())
        metrics["num_images"] = len(cow_embeddings)
        print(f"Updated class mean for '{args.cow_name}' (ID: {cow_id})")
    
    # Save checkpoint
    save_checkpoint(
        model=model,
        class_to_idx=class_to_idx,
        class_means=class_means,
        latent_dim=latent_dim,
        image_size=image_size,
        checkpoint_path=args.checkpoint,
    )
    
    # Save metrics
    save_metrics(metrics, args.metrics_file)
    
    # Create plots directory if it doesn't exist
    args.plot_dir.mkdir(exist_ok=True)
    
    # Plot embedding visualizations after each training session
    all_embeddings_plot_path = args.plot_dir / "all_embeddings.png"
    class_means_plot_path = args.plot_dir / "class_means.png"
    
    # Plot 1: All individual embedding points
    plot_all_embeddings(
        model, 
        class_to_idx, 
        class_means, 
        device, 
        all_embeddings_plot_path,
        current_cow_loader=train_loader,
        current_cow_id=cow_id,
        current_cow_name=args.cow_name
    )
    
    # Plot 2: Only class means
    plot_class_means(
        class_to_idx,
        class_means,
        class_means_plot_path
    )
    
    print(f"\n✓ Training complete for cow '{args.cow_name}'!")
    print(f"  Total cows in model: {len(class_to_idx)}")
    print(f"  Checkpoint saved to: {args.checkpoint}")
    print(f"  Metrics saved to: {args.metrics_file}")
    print(f"  All embeddings plot saved to: {all_embeddings_plot_path}")
    print(f"  Class means plot saved to: {class_means_plot_path}")


if __name__ == "__main__":
    main()

