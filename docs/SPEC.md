# 📽️ Content Authenticity Verification: Python Library + S3-backed Proof-of-Concept

This specification outlines a **minimal, no-database, no-always-on infrastructure** approach to providing cryptographic content authenticity for video and audio media. It is designed as a proof-of-concept that can scale from small independent creators to major platforms with minimal changes.

---

## 🔍 Purpose

To provide an open-source toolchain and S3-backed infrastructure that allows content creators to:

- ✅ Sign and verify the **authenticity** of a media file
- ⛔ Detect and **disprove manipulation**
- 🪪 Establish a verifiable timeline of creation and publication

---

## 🧩 Project Overview

- 🐍 **Language**: Python (library + CLI tool)
- 🪣 **Storage**: Amazon S3 public object storage only
- 🧾 **Infrastructure**: Stateless, no always-on services, no DBs
- 🔐 **Trust**: TLS-style certs, SHA-based digests, optional CA-level signing later

---

## 🧑‍💻 Audience & Use Cases

### 1. **Content Creators / Producers**

- **Input**: Single video file (e.g., `.mp4`, `.mov`, etc.)
- **Output**: A local directory containing:
  - A compressed reference video digest
  - An audio fingerprint
  - A metadata.json (capture time, optional GPS, user identity)
  - A signature file (SHA-256 + optional cert-chain)
- **Action**:
  - Run: `verifytool sign ./my_video.mp4`
  - Uploads result to: `https://verifybucket.s3.amazonaws.com/<auto_generated_id>/`
  - Returns short URL + pointer for verification

### 2. **Platforms / Distributors (e.g., YouTube, TikTok)**

- **Input**: Video or clip + URL of the signed package
- **Usage**: Run `verifytool check ./clip.mp4 --reference https://verifybucket.s3.amazonaws.com/xyz123/`
  - Can verify:
    - The clip matches original source content
    - Timestamp is within range
    - Optional geolocation or context match
- **Integration**: Embed badge or metadata in published version

### 3. **Consumers / Viewers**

- Can view a visual indicator if verification passes
- Can optionally download verification package or run `verifytool check` themselves
- Will be provided educational material to understand what a valid/invalid signature means

---

## 📦 Architecture

### Signing Workflow (Producer-side)

1. `sign()` CLI tool invoked on local machine
2. Generates:
   - Compressed reference video
   - Audio fingerprint (via Dejavu or equivalent)
   - `metadata.json` with timestamp, location, cert info
   - Digital signature of all the above
3. Stores in a temp local directory: `/output/video_title_digest_package/`
4. Zips and uploads to our free service endpoint
5. Server:
   - Unzips + validates structure
   - Verifies signature integrity + media format
   - Stores package in S3 with public read access

### Verification Workflow (Consumer / Platform)

1. `check()` CLI tool invoked with a video/clip file + S3 URL
2. Downloads reference digest
3. Compares:
   - Video hashes
   - Audio fingerprint matches
   - Metadata consistency (timestamp range, etc.)
4. Returns PASS/FAIL + human-readable explanation

---

## 🧪 File Structure (per verified asset)

```
my_video_package/
├── digest_video.mp4           # Resized, compressed reference
├── audio_fingerprint.json     # Output from audio fingerprinting
├── metadata.json              # JSON w/ timestamp, optional GPS, source
├── signature.txt              # SHA-256 signature over metadata + video
└── manifest.json              # Full manifest of hashes + file references
```

---

## 🚀 Hosting + Cost Model

- Publicly accessible S3 bucket (`verifybucket.s3.amazonaws.com`)
- All assets uploaded must pass validation
- No direct API keys or accounts needed to verify content
- Assets are static and retrieved directly via S3 URLs
- Cost is limited to:
  - Signature validation on upload
  - Occasional garbage collection for invalid/malformed files

---

## 🔐 Trust Model (Initial Phase)

- All signing is local and cryptographic
- Users may optionally include their own `.pem` certificate for extra identity confidence
- Future: support CA-issued signing certs
- Packages are uniquely identified by SHA-based ID

---

## 🧠 Next Steps

- [ ] Implement `sign()` and `check()` commands in Python
- [ ] Integrate video compression + audio fingerprinting tools
- [ ] Publish CLI tool on PyPI
- [ ] Deploy minimal upload endpoint that validates + writes to S3
- [ ] Publish S3 public viewer + JSON index for browsing
- [ ] Draft educational materials for creators, platforms, and consumers

---

Let us know if you're interested in contributing, adopting, or federating your own verification mirror or upload endpoint.

> ✅ _Our mission is simple: Prove what’s real. Reject what’s manipulated._
