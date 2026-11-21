# Local voice (Phase 3)

## November 16 hands-free increment

Performance follow-up: a measured 500-character Kokoro reply took 8.3 seconds to synthesize before playback, while a 150-character sample took 2.8 seconds. The app now speaks the first sentence (maximum 220 characters) and retains the full answer on screen. This improves long spoken replies but does not remove local model inference time or guarantee all answers are fast. Temporary playback WAV files are deleted after playback or Stop speech. Hands-free preference is saved and restored when the app launches; a live relaunch showed listening active. One owner-generated hands-free task, “open Spotify,” appeared succeeded with a macOS open callback in the app history, but recognition reliability across phrasings remains unmeasured.

The main window and menu-bar menu now have a hands-free toggle. While enabled and JARVIS is running, the existing macOS on-device recognizer listens for “Hey Jarvis”, “Okay Jarvis” or “OK Jarvis” followed by a command in the same utterance. After 1.6 seconds without a changed command transcription, it submits through the normal executive policy and approval path. The core displays listening state. A 60-second session restarts while enabled, speech playback pauses capture to avoid hearing JARVIS's own voice, Stop All or service disconnection turns listening off, and failed permission/recognition does not pretend listening continues. This is a first functional path using continuous recognition, not a dedicated low-power wake-word model. The user can turn it off at any time. Four parser cases and a live app on/off UI check passed; actual spoken wake/command accuracy, false-positive rate, and extended battery use still require owner testing.

## November 4 neural voice increment (supersedes macOS output below)

Owner feedback adjustment: speech uses structured answer text (or an action's message), excluding the UI notice and source/path metadata. Full details remain visible. Voice changed to bm_lewis at 1.18 speed for a brisker British delivery. This is an original stock neural voice, not an exact movie voice. Swift speech-content checks cover answer/notice separation and action-message playback.

Selected-result playback now uses project-local Kokoro ONNX with `bm_george` British English voice. `scripts/speak_neural.py` receives at most 600 characters over private stdin, generates audio locally, and replaces itself with afplay so Stop speech/Stop All/quit can terminate playback. No actor voice cloning is used. The runtime lives in `.runtime/voice`, with model and voice data in `models/voice`. Initial synthesis loads the model on each request; latency tuning is deferred by owner request. Generated WAV files currently remain under ignored `artifacts/`; cleanup and automatic spoken responses remain follow-up work. This is a Phase 3 increment, not full phase acceptance.

JARVIS uses the native macOS Speech framework and AVAudioEngine for explicit microphone sessions, and AVSpeechSynthesizer for speech output. No Whisper download or Python audio dependency is required. This trades universal language/device coverage for a smaller native installation.

## Use

1. Press **Mic** in the command bar. Only this gesture requests Speech Recognition and Microphone permissions. No recording starts at app launch.
2. Speak, then press **Stop mic**. This is a press-to-start/press-to-stop interaction, not a hold gesture. Sessions also stop on recognition completion/error or after 60 seconds.
3. The latest recognized text is appended to the command field. Review and edit it, then press **Execute**. Speech never automatically submits a command; execution controls are disabled while the mic starts/listens.
4. In a task with output, press **Read result** to speak that selected result. Use **Stop speech**, **Stop All**, or quit to stop playback.

**Stop All** immediately ends recording and playback even if the executive is disconnected. It discards the current in-progress recording transcript; it does not erase an existing command draft. Quit also cancels both. Cancelling while a system permission dialog is pending prevents a late permission response from starting recording.

## Privacy and availability

Every speech request sets `requiresOnDeviceRecognition = true`. There is no cloud fallback and no audio file persistence. Audio buffers are held by the native recognizer during a session. Accepted transcription goes into the normal command draft; it enters task history only if the user executes it.

The recognition language follows `Locale.current.identifier`. Availability depends on macOS, hardware, language, and locally available speech assets. Unsupported or temporarily unavailable recognition, denied permissions, missing input, and engine/recognition errors are shown in the command bar. Typed commands remain available. JARVIS does not install speech assets automatically or silently choose another language. If macOS cannot supply an on-device recognizer for the current locale, this implementation cannot transcribe; an optional separate local model engine would be future work.

Speech output uses a macOS voice for the current locale and reports when none is available. Voice installation is managed by macOS. JARVIS does not call a remote speech API.

Permission settings: **System Settings → Privacy & Security → Microphone / Speech Recognition**. Input selection: **System Settings → Sound**. The app bundle includes both required privacy descriptions.

## Verification performed

- `zsh scripts/build.sh`: successful Swift compilation and ad-hoc signing of `.build/JARVIS.app`.
- Compiled and ran an isolated controller smoke harness: initial idle state, repeated stop calls, empty speech no-op, and unchanged microphone/speech authorization state all passed. It did not call capture or request privacy permissions.
- Parsed the built `Info.plist`: both microphone and speech permission descriptions are present.
- Code inspection: capture callbacks are session-guarded; Stop All invalidates pending permission/capture callbacks; the UI's transcript callback only appends to the draft.

The installed SDK warns that the audio-node tap API is deprecated in macOS 27; it remains available and builds for the existing macOS 14 minimum. The compatibility implementation is intentional for now.

## Manual validation still required

No microphone recording, permission grant/denial UI, audible playback, recognition accuracy, installed-language support, offline-network test, or VoiceOver interaction was exercised in automated verification. On the target Mac:

- Launch and confirm no permission dialog or microphone activity until Mic is pressed.
- Grant permissions, disconnect networking, speak a short command, stop, and confirm it appears only in the draft. Check transcription accuracy before executing.
- Try permission denial, an unsupported locale/missing assets, and absent input; confirm an actionable status with working typed input.
- Stop All while listening, while permission is pending, and during playback; then quit during listening/playback. Confirm microphone/audio stop and do not restart.
- Verify 60-second capture timeout, repeated start/stop, selected-result playback, keyboard navigation, minimum window layout, and VoiceOver button labels.

## User-assisted smoke, 1 November 2026

The user accepted the microphone test. Native UI observations showed `Listening locally · en_IN`, followed by `Transcript added to command · review and press Execute`. A subsequent `Open calculator` task succeeded with independent `NSWorkspace.runningApplications` evidence for `com.apple.calculator`. This confirms one on-device capture→review→execution path on this Mac. Permission-denial, absent-device, offline-network, spoken-result playback, accessibility and repeated-session stress cases remain unverified.
