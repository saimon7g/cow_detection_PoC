"""
Load a trained contrastive autoencoder checkpoint and classify a single cow image
by nearest class centroid in the embedding space.

Example:
    python classify_cow.py --checkpoint cae_checkpoint.pt --image path/to/cow.jpg
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
from PIL import Image

from contrastive_autoencoder import ConvAutoencoder, build_transforms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify a cow image by embedding proximity.")
    parser.add_argument("--checkpoint", type=Path, default=Path("cae_checkpoint.pt"), help="Path to saved checkpoint.")
    parser.add_argument("--image", type=Path, required=True, help="Path to the cow image to classify.")
    parser.add_argument("--top-k", type=int, default=3, help="Show top-K nearest profiles.")
    return parser.parse_args()


@torch.no_grad()
def classify_image(args: argparse.Namespace) -> None:
    ckpt = torch.load(args.checkpoint, map_location="cpu")
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

    transform = build_transforms(image_size)
    img = Image.open(args.image).convert("RGB")
    tensor = transform(img).unsqueeze(0).to(device)

    _, embedding = model(tensor)
    embedding = embedding.cpu()

    distances = []
    for cls_idx, centroid in class_means.items():
        dist = torch.norm(embedding - centroid, dim=1).item()
        distances.append((dist, idx_to_class[cls_idx]))
    distances.sort(key=lambda x: x[0])

    top_k = min(args.top_k, len(distances))
    print(f"Top {top_k} nearest profiles for {args.image}:")
    for rank, (dist, name) in enumerate(distances[:top_k], start=1):
        print(f"{rank}. {name} (L2 distance {dist:.4f})")


def main() -> None:
    args = parse_args()
    classify_image(args)


if __name__ == "__main__":
    main()

