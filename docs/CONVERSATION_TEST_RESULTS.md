# Conversation acceptance results — 1 November 2026

Full regression suite: 86 run, 77 passed, 9 runtime-dependent skips. Separate native OpenJarvis suite: 8 passed. Native app rebuilt successfully; existing audio API deprecation warning remains.

Actual local-model samples (these are measured examples, not latency guarantees):

- **Hi** → Hello! How can I assist you today? (12.09 seconds)
- **Explain gravity and give one simple example.** → Gravity is the natural force that attracts objects with mass toward each other. For example, when you drop a ball, it falls to the ground due to Earth's gravity. (12.01 seconds)
- **Tell me this code word back: saffron42.** → saffron42 (11.44 seconds)
- **What code word did I just tell you?** → saffron42 (7.25 seconds)

No workspace effects occurred in these chat tests. The code-word follow-up used recent conversation context. Corrected local template uses existing Qwen3 weights. User acceptance is pending; subsequent milestones wait for that acceptance.
