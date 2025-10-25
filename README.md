# 🎬 ReelTrust

_**⚠️ NOTE: This product is a work in progress. Below explains planned features, not current capabilities.**_

**ReelTrust** is an open-source framework for media authenticity, designed to help creators, platforms, and consumers verify whether audio/video content is original, manipulated, or traceable to its source.

## Design Spec and Overview

See [docs/SPEC.md](docs/SPEC.md) for a full specification and writeup.

## 🚀 Goals

- Provide **proof of authenticity** for media content.
- Prevent **misinformation** through signed reference digests.
- Enable easy **integration** for platforms (e.g. YouTube, TikTok) to verify clips.
- Require **no always-on infrastructure** — using stateless Python tooling + public S3.

## ✨ Key Features

- One-step CLI to create signed packages
- Verifies both audio and video from a single input
- Public S3-compatible storage backend (no login required)
- Works entirely offline — signs content locally
- Future-proof design: supports third-party trust registries, optional CA signing

## 🧑‍💻 For Creators

### Create a Signed Package

```bash
reeltrust sign ./my_video.mp4 --user "creator@example.com" --gps "37.7749,-122.4194"
```

**Options:**

- `-o, --output` - Output directory (default: `.data/outputs`)
- `-u, --user` - User identity (username, email, etc.)
- `-g, --gps` - GPS coordinates as `'latitude,longitude'`
- `-w, --width` - Compressed video width (default: 240)

This command:

- Extracts a compressed reference video (240px digest)
- Generates an audio fingerprint using Chromaprint
- Packages metadata and timestamps
- Creates a signed manifest
- **Note:** S3 upload coming soon

Returns a verification package directory for later verification.

## 🎞️ For Platforms

### Verify a Video Against Its Package

```bash
reeltrust verify ./my_video.mp4 ./my_video_package/
```

**Options:**

- `-w, --width` - Width for compressed digest (default: 240)
- `-t, --threshold` - Minimum SSIM threshold for validation (default: 0.99)

**Verification Process:**

1. Validates package structure (manifest, signature, digest video)
2. Verifies manifest signature integrity
3. Confirms original video hash matches manifest
4. Recreates digest video using same compression pipeline
5. Compares digests via SHA-256 hash
6. Falls back to SSIM (structural similarity) if hashes differ
7. Validates frame counts are identical

**Output:**

- ✓ VERIFICATION PASSED - Video digest is authentic
- ✗ VERIFICATION FAILED - Video may have been tampered with
- Detailed check results and error messages

**Note:** Clip/timestamp verification and S3 reference support coming soon.

## 👀 For Viewers

- See a checkmark or badge on verified content
- Optionally download the signed package
- Educational resources explain what it means when content is verified vs unverifiable

## 📁 Package Contents

    my_video_package/
    ├── digest_video.mp4
    ├── audio_fingerprint.json
    ├── metadata.json
    ├── signature.txt
    └── manifest.json

## 🛠️ Tech Stack

- Python 3.x
- FFmpeg
- Dejavu (audio fingerprinting)
- Boto3 or similar S3-compatible uploader

## 📦 Architecture

No databases. No APIs. No secrets.

Everything is handled via:

- CLI tool
- Public S3 storage
- Signed local packages

## 📄 License

MIT (TBD)

---

## 🤝 Contributing

Want to contribute? Check out our [Contributing Guide](docs/CONTRIBUTING.md) to get started!

See also:

- [SPEC.md](docs/SPEC.md) - Full project specification
- [project_plan.md](docs/project_plan.md) - Roadmap and technical debt tracker
