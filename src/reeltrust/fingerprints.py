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
from typing import Any

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


def hamming_distance(hash1: int, hash2: int) -> int:
    """Calculate Hamming distance between two 64-bit hashes.

    Hamming distance is the number of bit positions where two hashes differ.
    Lower distance = more similar.

    Args:
        hash1: First 64-bit hash as integer
        hash2: Second 64-bit hash as integer

    Returns:
        Number of differing bits (0-64)
    """
    # XOR gives 1 where bits differ, then count the 1s
    return bin(hash1 ^ hash2).count('1')


def compare_perceptual_hashes(
    computed_data: bytes,
    stored_data: bytes,
    hash_size: int = 8,
    window_size: int = 60,
    fps: float = 30.0,
) -> dict[str, Any]:
    """Compare two sets of perceptual hashes (dHash or pHash) using windowed analysis.

    Uses non-overlapping 60-frame windows (~2 seconds at 30fps) to detect localized
    tampering. Takes the WORST (maximum) window mean as the verification metric to
    ensure brief tampering can't be hidden by averaging across a long authentic video.

    Args:
        computed_data: Binary hash data from the video being verified
        stored_data: Binary hash data from the original package
        hash_size: Hash size (default: 8 for 64-bit hashes)
        window_size: Frames per window (default: 60 = ~2 seconds at 30fps)
        fps: Frames per second for timestamp calculation (default: 30.0)

    Returns:
        Dictionary with comparison results:
        {
            'frame_count': int,
            'window_count': int,
            'worst_window_mean_distance': float,  # Maximum mean distance across all windows
            'overall_mean_distance': float,       # Mean across entire video (for reference)
            'max_frame_distance': int,            # Worst individual frame
            'perfect_match_pct': float,           # % of frames with perfect match
            'is_valid': bool,                     # True if worst window < threshold
            'worst_windows': list[dict],          # Top 3 worst windows with details
        }
    """
    bytes_per_hash = hash_size  # 8 bytes for 64-bit hash

    # Validate inputs
    if len(computed_data) != len(stored_data):
        return {
            'is_valid': False,
            'error': f'Hash data length mismatch: {len(computed_data)} vs {len(stored_data)} bytes'
        }

    if len(computed_data) % bytes_per_hash != 0:
        return {
            'is_valid': False,
            'error': f'Invalid hash data length: {len(computed_data)} (not multiple of {bytes_per_hash})'
        }

    frame_count = len(computed_data) // bytes_per_hash

    # Compute frame-by-frame Hamming distances
    distances = []
    perfect_matches = 0

    for i in range(frame_count):
        offset = i * bytes_per_hash

        # Unpack 8-byte hash as unsigned 64-bit little-endian integer
        computed_hash = struct.unpack('<Q', computed_data[offset:offset + bytes_per_hash])[0]
        stored_hash = struct.unpack('<Q', stored_data[offset:offset + bytes_per_hash])[0]

        # Calculate Hamming distance
        distance = hamming_distance(computed_hash, stored_hash)
        distances.append(distance)

        if distance == 0:
            perfect_matches += 1

    distances_array = np.array(distances)

    # Compute window-based metrics using non-overlapping windows
    window_means = []
    window_info = []

    for start_frame in range(0, frame_count, window_size):
        end_frame = min(start_frame + window_size, frame_count)
        window_distances = distances_array[start_frame:end_frame]
        window_mean = np.mean(window_distances)
        window_max = np.max(window_distances)

        # Find the frame with maximum distance within this window
        max_distance_idx = np.argmax(window_distances)
        max_distance_frame = start_frame + max_distance_idx
        max_distance_time = max_distance_frame / fps

        window_means.append(window_mean)

        # Format timestamps
        start_time = start_frame / fps
        end_time = end_frame / fps

        window_info.append({
            'start_frame': start_frame,
            'end_frame': end_frame,
            'start_time': f"{int(start_time // 60):02d}:{int(start_time % 60):02d}",
            'end_time': f"{int(end_time // 60):02d}:{int(end_time % 60):02d}",
            'mean_distance': round(float(window_mean), 2),
            'max_distance': int(window_max),
            'max_distance_frame': max_distance_frame,
            'max_distance_time': f"{int(max_distance_time // 60):02d}:{int(max_distance_time % 60):02d}",
        })

    # Sort windows by mean distance (worst first) and take top 3
    worst_windows = sorted(window_info, key=lambda w: w['mean_distance'], reverse=True)[:3]

    # Verification metric: worst window mean distance
    worst_window_mean = max(window_means)
    overall_mean_distance = np.mean(distances_array)
    max_frame_distance = int(np.max(distances_array))
    perfect_match_pct = (perfect_matches / frame_count) * 100

    # Threshold: Worst window mean should be very low for authentic videos
    # Even with re-encoding, perceptual hashes should differ by only 1-3 bits on average per window
    # Tampered windows will have much higher distances (10-30+ bits)
    threshold = 5.0  # bits
    is_valid = worst_window_mean < threshold

    return {
        'frame_count': frame_count,
        'window_count': len(window_means),
        'worst_window_mean_distance': round(worst_window_mean, 2),
        'overall_mean_distance': round(float(overall_mean_distance), 2),
        'max_frame_distance': max_frame_distance,
        'perfect_match_pct': round(perfect_match_pct, 2),
        'is_valid': is_valid,
        'threshold_bits': threshold,
        'worst_windows': worst_windows,
    }


def compare_frame_statistics(
    computed_stats: list[dict],
    stored_stats: list[dict],
    window_size: int = 60,
    fps: float = 30.0,
) -> dict[str, Any]:
    """Compare frame-by-frame YUV statistics using windowed analysis.

    Uses non-overlapping 60-frame windows (~2 seconds at 30fps) to detect localized
    tampering. Takes the WORST (minimum) correlation and WORST (maximum) MAD across
    all windows as the verification metrics.

    Args:
        computed_stats: Frame stats from video being verified
        stored_stats: Frame stats from original package
        window_size: Frames per window (default: 60 = ~2 seconds at 30fps)
        fps: Frames per second for timestamp calculation (default: 30.0)

    Returns:
        Dictionary with comparison results:
        {
            'frame_count': int,
            'window_count': int,
            'worst_window_correlation': float,  # Minimum correlation across all windows
            'worst_window_mad': float,          # Maximum MAD across all windows
            'overall_correlation': float,       # Correlation across entire video (for reference)
            'overall_mad': float,               # MAD across entire video (for reference)
            'is_valid': bool,                   # True if worst window passes thresholds
            'worst_windows': list[dict],        # Top 3 worst windows with details
        }
    """
    # Validate inputs
    if len(computed_stats) != len(stored_stats):
        return {
            'is_valid': False,
            'error': f'Frame count mismatch: {len(computed_stats)} vs {len(stored_stats)}'
        }

    if len(computed_stats) == 0:
        return {
            'is_valid': False,
            'error': 'No frame statistics to compare'
        }

    frame_count = len(computed_stats)
    channels = ['y_mean', 'y_std', 'u_mean', 'u_std', 'v_mean', 'v_std']

    # Extract all channel values as arrays
    computed_arrays = {}
    stored_arrays = {}
    for channel in channels:
        computed_arrays[channel] = np.array([frame[channel] for frame in computed_stats])
        stored_arrays[channel] = np.array([frame[channel] for frame in stored_stats])

    # Compute window-based metrics using non-overlapping windows
    window_correlations = []
    window_mads = []
    window_info = []

    for start_frame in range(0, frame_count, window_size):
        end_frame = min(start_frame + window_size, frame_count)

        # Compute metrics for this window across all channels
        window_channel_correlations = []
        window_channel_mads = []

        for channel in channels:
            computed_window = computed_arrays[channel][start_frame:end_frame]
            stored_window = stored_arrays[channel][start_frame:end_frame]

            # Correlation for this channel in this window
            if len(computed_window) > 1:  # Need at least 2 points for correlation
                correlation = np.corrcoef(computed_window, stored_window)[0, 1]
                # Handle NaN case (constant values)
                if np.isnan(correlation):
                    correlation = 1.0 if np.allclose(computed_window, stored_window) else 0.0
            else:
                correlation = 1.0 if np.allclose(computed_window, stored_window) else 0.0

            window_channel_correlations.append(correlation)

            # MAD for this channel in this window
            mad = np.mean(np.abs(computed_window - stored_window))
            window_channel_mads.append(mad)

        # Average across all channels for this window
        window_mean_correlation = np.mean(window_channel_correlations)
        window_mean_mad = np.mean(window_channel_mads)

        # Find worst frame in window (highest average MAD across all channels)
        frame_mads = []
        for i in range(start_frame, end_frame):
            frame_mad_sum = sum(
                abs(computed_arrays[ch][i] - stored_arrays[ch][i])
                for ch in channels
            )
            frame_mads.append(frame_mad_sum / len(channels))

        max_mad_idx = np.argmax(frame_mads)
        max_mad_frame = start_frame + max_mad_idx
        max_mad_value = frame_mads[max_mad_idx]
        max_mad_time = max_mad_frame / fps

        window_correlations.append(window_mean_correlation)
        window_mads.append(window_mean_mad)

        # Format timestamps
        start_time = start_frame / fps
        end_time = end_frame / fps

        window_info.append({
            'start_frame': start_frame,
            'end_frame': end_frame,
            'start_time': f"{int(start_time // 60):02d}:{int(start_time % 60):02d}",
            'end_time': f"{int(end_time // 60):02d}:{int(end_time % 60):02d}",
            'correlation': round(float(window_mean_correlation), 4),
            'mad': round(float(window_mean_mad), 2),
            'max_mad_frame': max_mad_frame,
            'max_mad_value': round(float(max_mad_value), 2),
            'max_mad_time': f"{int(max_mad_time // 60):02d}:{int(max_mad_time % 60):02d}",
        })

    # Sort windows by correlation (lowest first) and take top 3 worst
    worst_windows = sorted(window_info, key=lambda w: w['correlation'])[:3]

    # Verification metrics: worst window correlation (lowest) and worst window MAD (highest)
    worst_window_correlation = min(window_correlations)
    worst_window_mad = max(window_mads)

    # Overall metrics for reference
    overall_correlations = []
    overall_mads = []
    for channel in channels:
        overall_corr = np.corrcoef(computed_arrays[channel], stored_arrays[channel])[0, 1]
        if np.isnan(overall_corr):
            overall_corr = 1.0 if np.allclose(computed_arrays[channel], stored_arrays[channel]) else 0.0
        overall_correlations.append(overall_corr)

        overall_mad = np.mean(np.abs(computed_arrays[channel] - stored_arrays[channel]))
        overall_mads.append(overall_mad)

    overall_correlation = np.mean(overall_correlations)
    overall_mad = np.mean(overall_mads)

    # Thresholds:
    # - Correlation should be very high (>0.90) even in worst window
    # - MAD should be low (<0.8) even in worst window
    # Tighter MAD threshold reduces noise and focuses on true tampering
    correlation_threshold = 0.90
    mad_threshold = 0.8

    is_valid = (worst_window_correlation >= correlation_threshold and worst_window_mad < mad_threshold)

    return {
        'frame_count': frame_count,
        'window_count': len(window_correlations),
        'worst_window_correlation': round(worst_window_correlation, 4),
        'worst_window_mad': round(worst_window_mad, 2),
        'overall_correlation': round(float(overall_correlation), 4),
        'overall_mad': round(float(overall_mad), 2),
        'is_valid': is_valid,
        'correlation_threshold': correlation_threshold,
        'mad_threshold': mad_threshold,
        'worst_windows': worst_windows,
    }
