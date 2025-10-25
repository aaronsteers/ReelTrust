# Understanding SSIM (Structural Similarity Index)

## What is SSIM?

**SSIM** stands for **Structural Similarity Index Measure**. It's a way to measure how similar two images or videos are to each other, based on how humans actually perceive visual quality.

Think of it like comparing two photographs:

- A traditional approach would count every single different pixel (like counting every molecule that's different between two paintings)
- SSIM instead asks: "Do these look the same to a human eye?" (like stepping back and comparing the paintings as a person would)

## Why ReelTrust Uses SSIM

When verifying videos, ReelTrust needs to handle a real-world problem: **platforms re-encode videos**.

### The Problem

When you upload a video to YouTube, TikTok, or Instagram:

1. The platform compresses your video to save storage and bandwidth
1. Every pixel might be slightly different from your original
1. But the **content** is still the same - nothing was added, removed, or manipulated

### The Solution

Instead of requiring every pixel to match exactly, SSIM measures whether the **visual structure** is preserved:

- ✓ Are the edges in the same places?
- ✓ Is the brightness similar?
- ✓ Is the contrast similar?
- ✓ Do the patterns look the same?

## How to Read SSIM Scores

SSIM scores range from **-1 to 1**:

| Score | Meaning | Example |
|-------|---------|---------|
| **1.0** | Perfect match | Exact same file, no changes at all |
| **0.99** | Nearly identical | Same video, slightly re-compressed |
| **0.95** | Very similar | Re-encoded with different quality settings |
| **0.90** | Noticeably different | Heavy compression or minor edits |
| **0.80** | Significantly different | Major compression artifacts or content changes |
| **< 0.80** | Very different | Likely manipulated or heavily degraded |

### ReelTrust's Default Threshold

ReelTrust uses **0.99** as the default threshold, meaning:

- Videos must be 99% structurally similar to pass verification
- This allows for minor compression differences
- But catches any meaningful content manipulation

You can adjust this with the `--threshold` flag:

```bash
# Stricter (less tolerance for compression)
reeltrust verify video.mp4 package/ --threshold 0.99

# More tolerant (allows more compression artifacts)
reeltrust verify video.mp4 package/ --threshold 0.94

# Maximum strictness (exact file match only)
reeltrust verify video.mp4 package/ --strict
```

## Real-World Example

Let's say you recorded a video of a news event:

1. **Original**: You create a signed ReelTrust package (1.0 SSIM)
1. **YouTube Upload**: YouTube re-encodes it - still verifies! (~0.98-0.99 SSIM)
1. **Someone Edits It**: They remove a person from the frame - fails verification! (~0.75-0.85 SSIM)
1. **Deepfake**: Someone changes faces - fails verification! (~0.60-0.80 SSIM)

SSIM catches **meaningful changes** while tolerating **technical re-encoding**.

## How SSIM Works (Technical Overview)

SSIM compares three aspects between images:

1. **Luminance**: Overall brightness
1. **Contrast**: Range of light to dark
1. **Structure**: Patterns and edges

It analyzes these in small windows across the entire frame, then averages the results. This mimics how human vision works - we notice structural changes more than tiny pixel differences.

### ReelTrust's Sliding Window Approach

To prevent localized tampering from being hidden, ReelTrust uses a **sliding window** approach:

1. **Per-Frame Comparison**: FFmpeg computes SSIM for every frame individually
1. **Windowing**: Groups frames into ~5-second windows (150 frames at 30fps)
1. **Minimum Detection**: Returns the MINIMUM average SSIM across all windows

**Why this matters:**

- **Without windowing**: A 1-second deepfake in a 5-minute video could be averaged away
  - 299 seconds perfect (1.0) + 1 second tampered (0.6) = 0.9993 average ✓ Would pass!
- **With windowing**: Any 5-second window containing tampering will have low SSIM
  - Worst window with tampering = 0.6-0.8 ✗ Fails threshold!

This ensures that brief edits are detected equally well in short or long videos.

### Why Not Just Compare Pixels?

Traditional metrics like MSE (Mean Squared Error) treat all pixel differences equally:

- A slight shift in brightness = many "different" pixels
- But humans barely notice uniform brightness changes

SSIM is **perceptually aware** - it weights differences based on how humans see them.

## When SSIM Isn't Enough

SSIM works great for detecting:

- ✓ Content edits (adding/removing objects)
- ✓ Frame manipulation
- ✓ Major quality degradation
- ✓ Deepfakes and face swaps

SSIM may not catch:

- ✗ Audio changes (ReelTrust uses audio fingerprinting separately)
- ✗ Very subtle pixel-level manipulation
- ✗ Metadata changes

That's why ReelTrust uses **multiple verification methods**:

- SSIM for visual content
- Audio fingerprinting for sound
- SHA-256 hashes for exact matches
- Frame count validation

## Learn More

### Official Resources

- **Original SSIM Paper**: [Wang et al. (2004) - IEEE Transactions on Image Processing](https://www.cns.nyu.edu/~lcv/ssim/)
- **Wikipedia**: [Structural Similarity Index Measure](https://en.wikipedia.org/wiki/Structural_similarity_index_measure)
- **Interactive Tutorial**: [Imatest SSIM Documentation](https://www.imatest.com/docs/ssim/)

### Implementation

- **FFmpeg SSIM Filter**: Used by ReelTrust for video comparison
- **Python Implementation**: [scikit-image SSIM](https://scikit-image.org/docs/stable/auto_examples/transform/plot_ssim.html)
- **PyTorch Metrics**: [TorchMetrics SSIM](https://lightning.ai/docs/torchmetrics/stable/image/structural_similarity.html)

### Academic Background

> **Citation**: Wang, Z., Bovik, A. C., Sheikh, H. R., & Simoncelli, E. P. (2004). Image quality assessment: from error visibility to structural similarity. *IEEE Transactions on Image Processing*, 13(4), 600-612.

SSIM was developed at the Laboratory for Computational Vision at NYU and has become an industry standard for perceptual image quality assessment.

## Questions?

For more information about how ReelTrust uses SSIM:

- See [SPEC.md](SPEC.md) for the full technical specification
- Check out the [source code](../src/reeltrust/verifier.py) for implementation details
- Open an issue on [GitHub](https://github.com/aaronsteers/ReelTrust/issues) to ask questions

______________________________________________________________________

*Last updated: 2025-10-25*
