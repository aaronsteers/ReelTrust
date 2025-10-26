"""Perceptual fingerprinting for video content verification.

This module implements multiple fingerprinting techniques that can be pre-computed
from the original video and used to verify content authenticity independent of
compression artifacts:

- dHash (Difference Hash): 8-byte hash based on horizontal gradients
- pHash (Perceptual Hash): 8-byte DCT-based perceptual hash
- Frame Statistics: Y/U/V channel mean and standard deviation per frame
"""

import struct
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def compute_dhash(video_path: Path, hash_size: int = 8) -> tuple[bytes, float, int]:
    """Compute difference hash (dHash) for each frame in the video.

    dHash measures horizontal gradients - highly resistant to scaling and
    aspect ratio changes, moderately resistant to color changes.

    Args:
        video_path: Path to the video file
        hash_size: Size of the hash (default 8 for 8x8 = 64-bit hash)

    Returns:
        Tuple of (binary_data, compute_time_ms, frame_count)
        - binary_data: Concatenated 8-byte hashes (8 * num_frames bytes)
        - compute_time_ms: Time taken to compute in milliseconds
        - frame_count: Number of frames processed
    """
    start_time = time.time()

    cap = cv2.VideoCapture(str(video_path))
    hashes = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Convert BGR to RGB, then to PIL Image
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)

            # Resize to (hash_size + 1) x hash_size for horizontal gradient
            resized = pil_img.convert('L').resize(
                (hash_size + 1, hash_size),
                Image.Resampling.LANCZOS
            )
            pixels = np.array(resized)

            # Compute horizontal gradient (left < right = 1, else 0)
            diff = pixels[:, 1:] > pixels[:, :-1]

            # Convert boolean array to 64-bit integer
            hash_int = 0
            for i, bit in enumerate(diff.flatten()):
                if bit:
                    hash_int |= (1 << i)

            # Pack as 8-byte little-endian unsigned long
            hashes.append(struct.pack('<Q', hash_int))

    finally:
        cap.release()

    compute_time_ms = (time.time() - start_time) * 1000
    binary_data = b''.join(hashes)

    return binary_data, compute_time_ms, len(hashes)


def compute_phash(video_path: Path, hash_size: int = 8) -> tuple[bytes, float, int]:
    """Compute perceptual hash (pHash) for each frame using DCT.

    pHash uses Discrete Cosine Transform to capture frequency information.
    Highly resistant to scaling, aspect ratio, brightness, and contrast changes.

    Args:
        video_path: Path to the video file
        hash_size: Size of the hash (default 8 for 8x8 = 64-bit hash)

    Returns:
        Tuple of (binary_data, compute_time_ms, frame_count)
        - binary_data: Concatenated 8-byte hashes (8 * num_frames bytes)
        - compute_time_ms: Time taken to compute in milliseconds
        - frame_count: Number of frames processed
    """
    start_time = time.time()

    cap = cv2.VideoCapture(str(video_path))
    hashes = []

    # DCT size is typically 4x hash_size for better frequency resolution
    dct_size = hash_size * 4

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Resize to dct_size x dct_size
            resized = cv2.resize(gray, (dct_size, dct_size), interpolation=cv2.INTER_LANCZOS4)

            # Compute DCT
            dct = cv2.dct(np.float32(resized))

            # Extract top-left hash_size x hash_size (low frequencies)
            dct_low = dct[:hash_size, :hash_size]

            # Compute median
            median = np.median(dct_low)

            # Hash: 1 if above median, 0 if below
            diff = dct_low > median

            # Convert to 64-bit integer
            hash_int = 0
            for i, bit in enumerate(diff.flatten()):
                if bit:
                    hash_int |= (1 << i)

            # Pack as 8-byte little-endian unsigned long
            hashes.append(struct.pack('<Q', hash_int))

    finally:
        cap.release()

    compute_time_ms = (time.time() - start_time) * 1000
    binary_data = b''.join(hashes)

    return binary_data, compute_time_ms, len(hashes)


def compute_frame_statistics(video_path: Path) -> tuple[list[dict], float, int]:
    """Compute Y/U/V channel statistics for each frame.

    Computes mean and standard deviation for each YUV channel, providing
    a compact statistical summary of frame content.

    Args:
        video_path: Path to the video file

    Returns:
        Tuple of (stats_list, compute_time_ms, frame_count)
        - stats_list: List of dicts with Y/U/V mean/std for each frame
        - compute_time_ms: Time taken to compute in milliseconds
        - frame_count: Number of frames processed
    """
    start_time = time.time()

    cap = cv2.VideoCapture(str(video_path))
    stats = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Convert BGR to YUV
            yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)

            # Compute mean and std for each channel
            y_mean, y_std = cv2.meanStdDev(yuv[:, :, 0])
            u_mean, u_std = cv2.meanStdDev(yuv[:, :, 1])
            v_mean, v_std = cv2.meanStdDev(yuv[:, :, 2])

            stats.append({
                'y_mean': round(float(y_mean[0][0]), 2),
                'y_std': round(float(y_std[0][0]), 2),
                'u_mean': round(float(u_mean[0][0]), 2),
                'u_std': round(float(u_std[0][0]), 2),
                'v_mean': round(float(v_mean[0][0]), 2),
                'v_std': round(float(v_std[0][0]), 2),
            })

    finally:
        cap.release()

    compute_time_ms = (time.time() - start_time) * 1000

    return stats, compute_time_ms, len(stats)


def create_fingerprints(
    video_path: Path,
    output_dir: Path,
) -> dict:
    """Create all fingerprints for a video and save to disk.

    Computes dHash, pHash, and frame statistics from the original high-resolution
    video before compression. These fingerprints can be used to verify content
    authenticity independent of compression artifacts.

    Args:
        video_path: Path to the original video file
        output_dir: Directory to save fingerprint files (typically package/fingerprints/)

    Returns:
        Dictionary with fingerprint metadata for inclusion in manifest.json:
        {
            'source': 'original_video',
            'frame_count': 6458,
            'compute_time_ms': 4146,
            'files': {
                'dhash.bin': {'size_bytes': 51664, 'compute_time_ms': 1234},
                'phash.bin': {'size_bytes': 51664, 'compute_time_ms': 1456},
                'frame_stats.json': {'size_bytes': 257408, 'compute_time_ms': 1456}
            }
        }
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    total_start = time.time()

    print("  Computing perceptual fingerprints from original video...")

    # Compute dHash
    print("    - dHash (difference hash)...", end=' ', flush=True)
    dhash_data, dhash_time, dhash_frames = compute_dhash(video_path)
    dhash_path = output_dir / 'dhash.bin'
    dhash_path.write_bytes(dhash_data)
    print(f"{dhash_time:.0f}ms ({len(dhash_data):,} bytes, {dhash_frames} frames)")

    # Compute pHash
    print("    - pHash (perceptual hash)...", end=' ', flush=True)
    phash_data, phash_time, phash_frames = compute_phash(video_path)
    phash_path = output_dir / 'phash.bin'
    phash_path.write_bytes(phash_data)
    print(f"{phash_time:.0f}ms ({len(phash_data):,} bytes, {phash_frames} frames)")

    # Compute frame statistics
    print("    - Frame statistics (YUV)...", end=' ', flush=True)
    stats_data, stats_time, stats_frames = compute_frame_statistics(video_path)
    stats_path = output_dir / 'frame_stats.json'

    import json
    with open(stats_path, 'w') as f:
        json.dump(stats_data, f, separators=(',', ':'))

    stats_size = stats_path.stat().st_size
    print(f"{stats_time:.0f}ms ({stats_size:,} bytes, {stats_frames} frames)")

    total_time = (time.time() - total_start) * 1000

    # Verify all frame counts match
    assert dhash_frames == phash_frames == stats_frames, \
        f"Frame count mismatch: dHash={dhash_frames}, pHash={phash_frames}, stats={stats_frames}"

    print(f"  Total fingerprint compute time: {total_time:.0f}ms")

    return {
        'source': 'original_video',
        'frame_count': dhash_frames,
        'compute_time_ms': round(total_time, 2),
        'files': {
            'dhash.bin': {
                'size_bytes': len(dhash_data),
                'compute_time_ms': round(dhash_time, 2),
            },
            'phash.bin': {
                'size_bytes': len(phash_data),
                'compute_time_ms': round(phash_time, 2),
            },
            'frame_stats.json': {
                'size_bytes': stats_size,
                'compute_time_ms': round(stats_time, 2),
            },
        },
    }
