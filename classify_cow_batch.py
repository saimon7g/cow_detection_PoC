"""
Classify all images under a given folder using a trained contrastive autoencoder
checkpoint, writing results to a text file.

Example:
    python classify_cow_batch.py \
        --checkpoint cae_checkpoint.pt \
        --input-dir 7988559/test \
        --output results_test.txt \
        --top-k 3
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import torch
from PIL import Image

from contrastive_autoencoder import ConvAutoencoder, build_transforms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch classify cow images by embedding proximity.")
    parser.add_argument("--checkpoint", type=Path, default=Path("cae_checkpoint.pt"), help="Path to saved checkpoint.")
    parser.add_argument("--input-dir", type=Path, required=True, help="Folder containing images (scans subfolders).")
    parser.add_argument("--output", type=Path, default=Path("batch_results.txt"), help="Where to write results.")
    parser.add_argument("--top-k", type=int, default=3, help="Show top-K nearest profiles.")
    return parser.parse_args()


def list_images(root: Path) -> List[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    return sorted([p for p in root.rglob("*") if p.suffix.lower() in exts])


@torch.no_grad()
def load_model_and_centroids(checkpoint: Path) -> Tuple[ConvAutoencoder, dict, dict, int, int]:
    ckpt = torch.load(checkpoint, map_location="cpu")
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
def classify_image(
    model: ConvAutoencoder, class_means: dict, idx_to_class: dict, image_path: Path, transform, device, top_k: int
) -> List[Tuple[str, float]]:
    img = Image.open(image_path).convert("RGB")
    tensor = transform(img).unsqueeze(0).to(device)
    _, embedding = model(tensor)
    embedding = embedding.cpu()

    distances = []
    for cls_idx, centroid in class_means.items():
        dist = torch.norm(embedding - centroid, dim=1).item()
        distances.append((idx_to_class[cls_idx], dist))
    distances.sort(key=lambda x: x[1])
    return distances[: min(top_k, len(distances))]


def main() -> None:
    args = parse_args()
    model, class_means, idx_to_class, image_size, device = load_model_and_centroids(args.checkpoint)
    transform = build_transforms(image_size)

    images = list_images(args.input_dir)
    if not images:
        print(f"No images found under {args.input_dir}")
        return

    lines = []
    header = "image_path\tpredicted\tL2_distance\tothers(top-k)\n"
    lines.append(header)
    for img_path in images:
        distances = classify_image(model, class_means, idx_to_class, img_path, transform, device, args.top_k)
        top_label, top_dist = distances[0]
        others = "; ".join([f"{lbl}:{dist:.4f}" for lbl, dist in distances])
        lines.append(f"{img_path}\t{top_label}\t{top_dist:.4f}\t{others}\n")

    args.output.write_text("".join(lines))
    print(f"Wrote results for {len(images)} images to {args.output}")


if __name__ == "__main__":
    main()

