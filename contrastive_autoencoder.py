"""
Train a contrastive autoencoder on a directory of cow images where each
subfolder represents one individual. The model learns compact per-cow
clusters while maximizing separation between cows. After training it saves
an embedding scatter plot to visualize clusters.

Example:
    python contrastive_autoencoder.py \
        --data-root "/Users/saimon/Documents/Github/cow_detectation/7988559" \
        --epochs 10 \
        --batch-size 16
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Tuple

import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.manifold import TSNE
from torch.utils.data import DataLoader
from torchvision import datasets, transforms


def build_transforms(image_size: int) -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ]
    )


class ConvAutoencoder(nn.Module):
    def __init__(self, latent_dim: int = 64, image_size: int = 224):
        super().__init__()
        assert image_size % 8 == 0, "image_size must be divisible by 8 for this architecture."
        self.feature_h = image_size // 8  # spatial size after three stride-2 convs
        # Encoder
        self.encoder = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
            nn.ReLU(inplace=True),
        )
        self.enc_proj = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * self.feature_h * self.feature_h, 256),
            nn.ReLU(inplace=True),
            nn.Linear(256, latent_dim),
        )
        # Decoder mirrors encoder
        self.dec_proj = nn.Sequential(
            nn.Linear(latent_dim, 256),
            nn.ReLU(inplace=True),
            nn.Linear(256, 128 * self.feature_h * self.feature_h),
            nn.ReLU(inplace=True),
        )
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(128, 64, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(64, 32, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(32, 3, kernel_size=3, stride=2, padding=1, output_padding=1),
            nn.Tanh(),
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        x = self.encoder(x)
        z = self.enc_proj(x)
        return z

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        z = self.dec_proj(z)
        z = z.view(z.size(0), 128, self.feature_h, self.feature_h)
        x_hat = self.decoder(z)
        return x_hat

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        z = self.encode(x)
        x_hat = self.decode(z)
        return x_hat, z


def supervised_contrastive_loss(features: torch.Tensor, labels: torch.Tensor, temperature: float = 0.1) -> torch.Tensor:
    """Supervised contrastive loss (SupCon). If a sample has no positives in the batch it is skipped."""
    device = features.device
    features = F.normalize(features, dim=1)
    logits = torch.matmul(features, features.T) / temperature

    # mask to remove self-comparisons
    logits_mask = ~torch.eye(logits.size(0), dtype=bool, device=device)
    logits = logits.masked_select(logits_mask).view(logits.size(0), -1)

    labels = labels.contiguous()
    mask = labels.unsqueeze(0) == labels.unsqueeze(1)
    mask = mask.masked_select(logits_mask).view(logits.size(0), -1)

    exp_logits = torch.exp(logits)
    log_prob = logits - torch.log(exp_logits.sum(dim=1, keepdim=True) + 1e-12)

    # Only keep positives for each anchor
    mean_log_prob_pos = (mask * log_prob).sum(dim=1) / (mask.sum(dim=1) + 1e-9)
    # Skip anchors without positives
    valid = mask.sum(dim=1) > 0
    loss = -mean_log_prob_pos[valid].mean() if valid.any() else torch.tensor(0.0, device=device)
    return loss


def prepare_train_loader(
    train_root: Path, image_size: int, batch_size: int, device: torch.device
) -> DataLoader:
    transform = build_transforms(image_size)
    train_ds = datasets.ImageFolder(str(train_root), transform=transform)
    # Shuffle across cows to mix positives and negatives per batch
    pin_mem = device.type == "cuda"
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=pin_mem
    )
    return train_loader


def train(
    model: ConvAutoencoder,
    train_loader: DataLoader,
    device: torch.device,
    epochs: int,
    lr: float,
    contrastive_weight: float,
) -> None:
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    for epoch in range(1, epochs + 1):
        model.train()
        running_recon, running_contrast = 0.0, 0.0
        for imgs, labels in train_loader:
            imgs, labels = imgs.to(device), labels.to(device)
            opt.zero_grad()
            recon, z = model(imgs)
            recon_loss = F.mse_loss(recon, imgs)
            con_loss = supervised_contrastive_loss(z, labels)
            loss = recon_loss + contrastive_weight * con_loss
            loss.backward()
            opt.step()
            running_recon += recon_loss.item() * imgs.size(0)
            running_contrast += con_loss.item() * imgs.size(0)
        n = len(train_loader.dataset)
        print(
            f"Epoch {epoch:02d}/{epochs} | recon {running_recon / n:.4f} | "
            f"contrast {running_contrast / n:.4f}"
        )


@torch.no_grad()
def extract_embeddings(model: ConvAutoencoder, loader: DataLoader, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    embs, labels_all = [], []
    for imgs, labels in loader:
        imgs = imgs.to(device)
        z = model.encode(imgs)
        embs.append(z.cpu())
        labels_all.append(labels)
    return torch.cat(embs), torch.cat(labels_all)


def plot_embeddings(embs: torch.Tensor, labels: torch.Tensor, class_names, out_path: Path) -> None:
    tsne = TSNE(n_components=2, init="pca", learning_rate="auto", perplexity=10)
    reduced = tsne.fit_transform(embs.numpy())
    plt.figure(figsize=(10, 8))
    for cls_idx in torch.unique(labels):
        idx = labels == cls_idx
        plt.scatter(reduced[idx, 0], reduced[idx, 1], label=class_names[cls_idx], s=20, alpha=0.8)
    plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize="small", ncol=2)
    plt.title("Cow embeddings (t-SNE)")
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    print(f"Saved embedding plot to {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Contrastive autoencoder for cow clustering.")
    parser.add_argument(
        "--train-data-root",
        type=Path,
        default=Path("/Users/saimon/Documents/Github/cow_detectation/7988559/train"),
        help="Directory containing per-class train subfolders (ImageFolder layout).",
    )
    parser.add_argument("--epochs", type=int, default=8, help="Number of training epochs.")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size.")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate.")
    parser.add_argument("--latent-dim", type=int, default=64, help="Size of latent vector.")
    parser.add_argument("--contrastive-weight", type=float, default=0.2, help="Weight for contrastive loss.")
    parser.add_argument("--image-size", type=int, default=224, help="Square resize for images.")
    parser.add_argument(
        "--plot-path",
        type=Path,
        default=Path("embedding_plot.png"),
        help="Where to save the t-SNE scatter plot.",
    )
    parser.add_argument(
        "--save-path",
        type=Path,
        default=Path("cae_checkpoint.pt"),
        help="Where to save trained weights and class centroids.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    train_loader = prepare_train_loader(args.train_data_root, args.image_size, args.batch_size, device)
    model = ConvAutoencoder(latent_dim=args.latent_dim, image_size=args.image_size).to(device)
    train(
        model=model,
        train_loader=train_loader,
        device=device,
        epochs=args.epochs,
        lr=args.lr,
        contrastive_weight=args.contrastive_weight,
    )

    # Extract embeddings on train set for plotting and centroids
    train_embs, train_labels = extract_embeddings(model, train_loader, device)
    plot_embeddings(train_embs, train_labels, train_loader.dataset.classes, args.plot_path)

    class_means = {}
    for cls_idx in torch.unique(train_labels):
        mask = train_labels == cls_idx
        class_means[int(cls_idx.item())] = train_embs[mask].mean(dim=0)

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "class_to_idx": train_loader.dataset.class_to_idx,
            "class_means": {k: v.cpu() for k, v in class_means.items()},
            "latent_dim": args.latent_dim,
            "image_size": args.image_size,
        },
        args.save_path,
    )
    print(f"Saved checkpoint to {args.save_path}")


if __name__ == "__main__":
    main()


