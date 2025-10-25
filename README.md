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

Example usage:

    reeltrust sign ./my_video.mp4

This command:

- Extracts a compressed reference video
- Generates an audio fingerprint
- Packages metadata and timestamps
- Signs the result
- Uploads to a public S3 location

Returns a short URL or asset pointer for later verification.

## 🎞️ For Platforms

Example usage:

    reeltrust verify ./clip.mp4 --reference https://s3.example.com/abcd123/

Verifies:

- That a clip matches known signed footage
- Timestamp falls within valid capture window
- Optional GPS or cert data

Returns a verdict and a public proof log.

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
