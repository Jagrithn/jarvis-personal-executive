import AVFoundation
import Speech
import SwiftUI

/// Explicit, bounded microphone sessions. No server recognizer or audio persistence.
@MainActor
final class VoiceController: NSObject, ObservableObject, AVSpeechSynthesizerDelegate {
    @Published private(set) var recording = false
    @Published private(set) var preparing = false
    @Published private(set) var speaking = false
    @Published private(set) var handsFreeEnabled = false
    @Published private(set) var transcript = ""
    @Published private(set) var status = "Voice idle · on-device only · press mic to begin"
    let language = Locale.current.identifier
    private var engine: AVAudioEngine?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var recognition: SFSpeechRecognitionTask?
    private var recognizer: SFSpeechRecognizer?
    private var session = UUID()
    private var deadline: Task<Void, Never>?
    private var deliver: ((String) -> Void)?
    private let synthesizer = AVSpeechSynthesizer()
    private var neuralProcess: Process?
    private var wakeDelivery: ((String) -> Void)?
    private var wakeCandidate = ""
    private var wakeSilence: Task<Void, Never>?

    static func commandAfterWakePhrase(_ text: String) -> String? {
        for phrase in ["hey jarvis", "okay jarvis", "ok jarvis"] {
            if let range = text.range(of: phrase, options: .caseInsensitive) {
                let suffix = text[range.upperBound...].trimmingCharacters(in: .whitespacesAndNewlines)
                return suffix.trimmingCharacters(in: CharacterSet(charactersIn: ",.!? "))
            }
        }
        return nil
    }

    func toggleHandsFree(deliver: @escaping (String) -> Void) {
        if handsFreeEnabled {
            handsFreeEnabled = false
            wakeDelivery = nil
            wakeSilence?.cancel()
            stopCapture(keepTranscript: false)
            status = "Hands-free listening off"
        } else {
            handsFreeEnabled = true
            wakeDelivery = deliver
            resumeHandsFreeIfNeeded()
        }
    }

    func resumeHandsFreeIfNeeded() {
        guard handsFreeEnabled, !recording, !preparing, !speaking else { return }
        toggleCapture { _ in }
        status = "Hands-free listening · say Hey Jarvis and your command"
    }

    override init() {
        super.init()
        synthesizer.delegate = self
    }

    func toggleCapture(deliver: @escaping (String) -> Void) {
        if recording || preparing { stopCapture(keepTranscript: true); return }
        stopSpeaking()
        transcript = ""
        wakeCandidate = ""
        self.deliver = deliver
        let current = UUID()
        session = current
        preparing = true
        status = "Checking on-device recognition for \(language)…"
        Task {
            // Check capability before asking for privacy permissions. Never fall back to a server.
            guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: language)),
                  recognizer.supportsOnDeviceRecognition else {
                finishPreparation(current, message: "On-device speech unavailable for \(language). Use typed commands.")
                return
            }
            let speech = await withCheckedContinuation { continuation in
                SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0) }
            }
            guard session == current else { return }
            guard speech == .authorized else {
                finishPreparation(current, message: "Speech permission denied or restricted. Check System Settings → Privacy & Security → Speech Recognition.")
                return
            }
            let microphone = await AVCaptureDevice.requestAccess(for: .audio)
            guard session == current else { return }
            guard microphone else {
                finishPreparation(current, message: "Microphone permission denied. Check System Settings → Privacy & Security → Microphone.")
                return
            }
            guard recognizer.isAvailable else {
                finishPreparation(current, message: "Speech recognizer currently unavailable for \(language). Use typed commands.")
                return
            }
            startCapture(recognizer, session: current)
        }
    }

    private func finishPreparation(_ current: UUID, message: String) {
        guard session == current else { return }
        preparing = false
        deliver = nil
        handsFreeEnabled = false
        wakeDelivery = nil
        status = message
    }

    private func startCapture(_ recognizer: SFSpeechRecognizer, session current: UUID) {
        let engine = AVAudioEngine()
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.requiresOnDeviceRecognition = true
        request.shouldReportPartialResults = true
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else {
            finishPreparation(current, message: "No usable microphone input. Select an input in System Settings → Sound.")
            return
        }
        self.engine = engine
        self.request = request
        self.recognizer = recognizer
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in request.append(buffer) }
        recognition = recognizer.recognitionTask(with: request) { [weak self] result, error in
            let text = result?.bestTranscription.formattedString
            let final = result?.isFinal == true
            let failure = error?.localizedDescription
            Task { @MainActor in
                guard let self, self.session == current else { return }
                if let text { self.transcript = text }
                if self.handsFreeEnabled, let text,
                   let command = Self.commandAfterWakePhrase(text), !command.isEmpty,
                   command != self.wakeCandidate {
                    self.wakeCandidate = command
                    self.wakeSilence?.cancel()
                    self.wakeSilence = Task { [weak self] in
                        try? await Task.sleep(for: .milliseconds(1600))
                        guard !Task.isCancelled, let self, self.session == current,
                              self.wakeCandidate == command, self.handsFreeEnabled else { return }
                        self.stopCapture(keepTranscript: false)
                        self.status = "Heard: \(command)"
                        self.wakeDelivery?(command)
                    }
                }
                if final || failure != nil {
                    if self.handsFreeEnabled {
                        let command = Self.commandAfterWakePhrase(self.transcript)
                        self.stopCapture(keepTranscript: false)
                        if let command, !command.isEmpty { self.wakeDelivery?(command) }
                        else if failure == nil { self.resumeHandsFreeIfNeeded() }
                        else { self.handsFreeEnabled = false; self.wakeDelivery = nil }
                    } else { self.stopCapture(keepTranscript: true) }
                    if let failure { self.status = "On-device recognition stopped: \(failure). Review any captured text; typed commands remain available." }
                }
            }
        }
        do {
            engine.prepare()
            try engine.start()
            preparing = false
            recording = true
            status = "Listening locally · \(language) · press Stop mic when done (60-second limit)"
            deadline = Task { [weak self] in
                try? await Task.sleep(for: .seconds(60))
                guard !Task.isCancelled, let self, self.session == current else { return }
                if self.handsFreeEnabled {
                    self.stopCapture(keepTranscript: false)
                    self.resumeHandsFreeIfNeeded()
                } else { self.stopCapture(keepTranscript: true) }
            }
        } catch {
            stopCapture(keepTranscript: false)
            handsFreeEnabled = false
            wakeDelivery = nil
            status = "Microphone could not start: \(error.localizedDescription)"
        }
    }

    func stopCapture(keepTranscript: Bool) {
        session = UUID() // Ignore late permission and recognition callbacks after cancellation.
        wakeSilence?.cancel()
        wakeSilence = nil
        deadline?.cancel()
        deadline = nil
        if let engine { engine.stop(); engine.inputNode.removeTap(onBus: 0) }
        request?.endAudio()
        recognition?.cancel()
        engine = nil
        request = nil
        recognition = nil
        recognizer = nil
        recording = false
        preparing = false
        if keepTranscript && !transcript.isEmpty {
            deliver?(transcript)
            status = "Transcript added to command · review and press Execute"
        } else { status = "Voice stopped · no command submitted" }
        deliver = nil
    }

    func speak(_ text: String) {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        stopCapture(keepTranscript: true)
        stopSpeaking()
        guard let resources = Bundle.main.resourceURL,
              let data = try? Data(contentsOf: resources.appendingPathComponent("config.json")),
              let config = try? JSONSerialization.jsonObject(with: data) as? [String: String],
              let root = config["root"] else {
            status = "Neural voice configuration unavailable"
            return
        }
        let child = Process()
        child.executableURL = URL(fileURLWithPath: root + "/.runtime/voice/bin/python")
        child.arguments = [root + "/scripts/speak_neural.py"]
        let input = Pipe()
        child.standardInput = input
        child.standardOutput = FileHandle.nullDevice
        child.standardError = FileHandle.nullDevice
        child.terminationHandler = { [weak self] process in
            Task { @MainActor in
                guard let self, self.neuralProcess === process else { return }
                self.speaking = false
                self.neuralProcess = nil
                self.status = process.terminationStatus == 0 ? "Speech finished · voice idle" : "Neural speech failed · check voice runtime"
                self.resumeHandsFreeIfNeeded()
            }
        }
        do {
            try child.run()
            neuralProcess = child
            speaking = true
            status = "Generating local neural speech…"
            let payload = try JSONSerialization.data(withJSONObject: ["text": String(text.prefix(220))])
            try input.fileHandleForWriting.write(contentsOf: payload)
            try input.fileHandleForWriting.close()
        } catch { status = "Neural voice unavailable: " + error.localizedDescription }
    }

    func stopSpeaking() {
        let wasSpeaking = speaking
        neuralProcess?.terminate()
        neuralProcess = nil
        synthesizer.stopSpeaking(at: .immediate)
        speaking = false
        if wasSpeaking { status = "Speech stopped · voice idle" }
    }

    func stopAll() {
        handsFreeEnabled = false
        wakeDelivery = nil
        stopCapture(keepTranscript: false)
        stopSpeaking()
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor in
            guard !self.synthesizer.isSpeaking else { return }
            self.speaking = false
            self.status = "Speech finished · voice idle"
        }
    }
}
