# Trust Dynamics and Adversarial Scenarios in ReelTrust

## 🧭 Four Actor Scenarios in ReelTrust Verification

This issue outlines the four major use cases for authenticity verification through ReelTrust. Each case involves different motivations and verification challenges. This categorization helps clarify the scope of what ReelTrust *can* and *cannot* prove, and where our system provides meaningful leverage — even in adversarial cases.

---

### **1. Honest Actor Using ReelTrust**

- 🔒 Publishes signed digest + optional clip fingerprint metadata
- 🎞️ Provides full metadata: cropping, offsets, timestamps
- ✅ Verification is trivial and strong
- 📢 _Advertises_ the ReelTrust URI or embeds it in content

✅ This is the **primary target use case**. ReelTrust empowers creators to preemptively prove their video’s authenticity.

---

### **2. Malicious Actor With Doctored Content, Not Advertising ReelTrust**

- ❌ Does not link to ReelTrust URI
- 🙅‍♂️ No declared offset, no fingerprint claim
- 🫥 Avoids verification precisely because they know it would fail

🧠 **Key Point**: _ReelTrust makes no claim about unauthenticated videos._  
However, our system enables good actors to **disarm disinformation** by later verifying that those videos **do not match** signed originals.

---

### **3. Malicious Actor Implying Authenticity, Without ReelTrust URI**

- 🚨 _This is the most dangerous case._
- The actor publishes doctored media without ReelTrust but **attempts to impersonate** a credible source.
- Viewers may assume the video is real, even without metadata.
- 🤔 The actor hopes **no one challenges the content.**

🧪 What can ReelTrust do?

- ❓ Use heuristic methods to detect approximate matches (e.g. clip offset detection, facial vectors)
- 🧩 Auto-guess timestamps, offsets, or clip fingerprints
- ❌ Attempt to *disprove* the video by showing divergence from signed media

This scenario requires advanced tooling, but **is partially addressable** with the right heuristics and enough confidence.

---

### **4. Original Creator Presents Their Original Video as Counter-Proof**

- 🗂️ Creator still holds the original high-fidelity file
- 🔐 That file matches the exact file hash from the signed ReelTrust package
- 🔁 They can re-verify their own digest and provide proof that a forgery does not match
- ✅ This proves that their version is authentic and the alternative is a forgery

This enables **strong, after-the-fact defense** even if doctored content is widely circulated.

---

## 🔐 Strategic Insight

> **ReelTrust is not only a proactive authenticity tool — it is also a reactive defense system**  
> that empowers truth-tellers to respond with cryptographic evidence _after_ misinformation has spread.

This framing will guide future work on auto-detection, heuristics, and downstream verification tooling.
