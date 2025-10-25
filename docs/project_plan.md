# ReelTrust Project Plan & Technical Debt

This document tracks technical debt and future enhancements accumulated during the POC phase.

## Current Status (POC Phase)

### ✅ Implemented Features

1. **Video Compression** - Compress videos to 240px width reference digest
1. **Audio Fingerprinting** - Using Chromaprint/AcoustID for audio fingerprinting
1. **Metadata Generation** - Extract and store video metadata, timestamps, user identity
1. **Signature Generation** - SHA-256 hashing of manifest (placeholder for future cryptographic signing)
1. **CLI Tool** - `reeltrust sign` command to create verification packages
1. **Package Structure** - Organized output with manifest, metadata, digest video, audio fingerprint, and signature

### 🔧 Known Technical Debt

#### High Priority

1. **Cryptographic Signing** (Currently: SHA-256 hashing only)
   - **Current**: Using SHA-256 hash as a placeholder signature
   - **Future**: Implement proper cryptographic signing with RSA/ECDSA
   - **Future**: Support user-provided `.pem` certificates
   - **Future**: Support CA-issued signing certificates
   - **Location**: `src/reeltrust/signature.py` - `create_signature()` function
   - **Note**: Added reminder in signature.json output
1. **Verification Functionality**
   - **Current**: Only signing is implemented
   - **Future**: Implement `reeltrust check` command to verify packages
   - **Future**: Compare video hashes, audio fingerprints, validate signatures
   - **Future**: Return PASS/FAIL + human-readable explanations
1. **S3 Upload Integration**
   - **Current**: Packages created locally only
   - **Future**: Upload signed packages to S3 bucket
   - **Future**: Generate shareable S3 URLs
   - **Future**: Server-side validation endpoint

#### Medium Priority

1. **Audio Fingerprinting Library**
   - **Current**: Using pyacoustid (Chromaprint)
   - **Note**: Originally wanted to use Dejavu but it's Python 2 only
   - **Future**: Evaluate if Chromaprint is sufficient or if we need alternatives
   - **Future**: Consider implementing custom fingerprinting if needed for verification matching
1. **System Dependencies Documentation**
   - **Current**: Requires `ffmpeg` and `chromaprint` (fpcalc) to be installed via brew/system
   - **Future**: Add clear documentation about system dependencies
   - **Future**: Consider Docker container for consistent environment
   - **Future**: Add dependency checks to CLI with helpful error messages
1. **GPS Metadata**
   - **Current**: Supports GPS input but not extracted from video EXIF/metadata
   - **Future**: Auto-extract GPS from video metadata if available
   - **Future**: Support mobile device capture metadata

#### Low Priority

1. **Error Handling**

   - **Future**: More granular error messages
   - **Future**: Graceful handling of videos without audio
   - **Future**: Validation of input video formats

1. **Compression Options**

   - **Current**: Fixed 240px width, CRF 32
   - **Future**: Allow configurable compression levels
   - **Future**: Optimize compression settings for different use cases

1. **Performance**

   - **Future**: Progress bars for long operations
   - **Future**: Parallel processing where applicable
   - **Future**: Optimize for large video files

1. **Testing**

   - **Future**: Unit tests for all modules
   - **Future**: Integration tests for full workflow
   - **Future**: Test with various video formats and edge cases

## Architecture Notes

### Current File Structure

```
src/reeltrust/
├── __init__.py
├── cli.py                    # CLI entry point
├── signer.py                 # Main signing orchestrator
├── video_processor.py        # Video compression & hashing
├── audio_fingerprint.py      # Audio fingerprinting (Chromaprint)
├── metadata.py               # Metadata extraction & generation
└── signature.py              # Manifest & signature generation
```

### Output Package Structure

```
sample-vid_package/
├── digest_video.mp4           # Compressed 240px reference video
├── audio_fingerprint.json     # Chromaprint audio fingerprint
├── metadata.json              # Video metadata & creation info
├── manifest.json              # File hashes & package manifest
└── signature.json             # SHA-256 hash (future: cryptographic signature)
```

## Future Milestones

### Phase 2: Verification

- Implement `reeltrust check` command
- Video and audio matching logic
- Signature verification
- Visual verification reports

### Phase 3: S3 Integration

- Upload endpoint
- Public S3 bucket setup
- URL generation and sharing
- Server-side validation

### Phase 4: Advanced Signing

- RSA/ECDSA signatures
- Certificate chain support
- CA integration
- Key management utilities

### Phase 5: Platform Integration

- Python SDK for platforms
- API documentation
- Badge/embeds for verified content
- Webhook notifications

______________________________________________________________________

**Last Updated**: 2025-10-25
**POC Version**: 0.1.0
