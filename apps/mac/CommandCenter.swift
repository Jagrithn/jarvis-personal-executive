import SwiftUI
import AppKit

private enum HUD {
    static let cyan = Color(red: 0.51, green: 0.72, blue: 0.76)
    static let ink = Color(red: 0.035, green: 0.047, blue: 0.061)
    static let panel = Color(red: 0.065, green: 0.080, blue: 0.100)
    static let muted = Color(red: 0.57, green: 0.65, blue: 0.69)
    static let line = cyan.opacity(0.11)
}
private struct HUDButton: ButtonStyle {
    var primary = false
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 11, weight: .semibold, design: .monospaced))
            .padding(.horizontal, 14).padding(.vertical, 10)
            .foregroundStyle(primary ? HUD.ink : HUD.cyan)
            .background(primary ? HUD.cyan.opacity(configuration.isPressed ? 0.6 : 1) : HUD.cyan.opacity(configuration.isPressed ? 0.18 : 0.06))
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(HUD.line))
    }
}
private struct GridBackdrop: View {
    var body: some View {
        Canvas { context, size in
            var grid = Path()
            for x in stride(from: CGFloat(0), to: size.width, by: 32) {
                grid.move(to: CGPoint(x: x, y: 0)); grid.addLine(to: CGPoint(x: x, y: size.height))
            }
            for y in stride(from: CGFloat(0), to: size.height, by: 32) {
                grid.move(to: CGPoint(x: 0, y: y)); grid.addLine(to: CGPoint(x: size.width, y: y))
            }
            context.stroke(grid, with: .color(HUD.cyan.opacity(0.035)), lineWidth: 0.5)
        }.allowsHitTesting(false).accessibilityHidden(true)
    }
}
private struct CoreDisplay: View {
    let connected: Bool
    let paused: Bool
    let active: Int
    var listening = false
    var speaking = false
    var expanded = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var tint: Color { !connected ? HUD.muted : paused ? .orange : HUD.cyan }
    private static let nodes: [(Double, Double, Double)] = (0..<120).map { index in
        let y = 1.0 - (Double(index) + 0.5) * 2.0 / 120.0
        let radius = sqrt(max(0, 1 - y * y))
        let theta = Double(index) * 2.3999632297
        return (cos(theta) * radius, y * 0.84, sin(theta) * radius * 0.84)
    }
    private static let edges: [(Int, Int)] = {
        var result: [(Int, Int)] = []
        for i in nodes.indices {
            for j in (i + 1)..<nodes.count {
                let a = nodes[i], b = nodes[j]
                let distance = pow(a.0-b.0, 2) + pow(a.1-b.1, 2) + pow(a.2-b.2, 2)
                if distance < 0.16 { result.append((i, j)) }
            }
        }
        return result
    }()
    var body: some View {
        ZStack {
            Circle().fill(tint.opacity(0.035)).frame(width: 220, height: 220).blur(radius: 10)
            Circle().stroke(tint.opacity(0.12), lineWidth: 1).frame(width: 224, height: 224)
            Circle().stroke(tint.opacity(0.22), style: StrokeStyle(lineWidth: 1, dash: [2, 8])).frame(width: 206, height: 206)
            Image(systemName: "brain.head.profile")
                .font(.system(size: 102, weight: .ultraLight))
                .foregroundStyle(tint.opacity(0.18)).accessibilityHidden(true)
            TimelineView(.animation(minimumInterval: 1.0 / 30.0, paused: reduceMotion)) { timeline in
                let angle = reduceMotion ? 0.0 : timeline.date.timeIntervalSinceReferenceDate * 0.22
                Canvas { context, size in
                    let scale = min(size.width, size.height) * 0.39
                    let points: [(CGPoint, Double)] = Self.nodes.map { x, y, z in
                        let rotatedX = x * cos(angle) + z * sin(angle)
                        let depth = -x * sin(angle) + z * cos(angle)
                        let perspective = 1.0 + depth * 0.15
                        return (CGPoint(x: size.width / 2 + CGFloat(rotatedX * perspective) * scale,
                                        y: size.height / 2 + CGFloat(y * perspective) * scale), depth)
                    }
                    for (i, j) in Self.edges {
                        var line = Path()
                        line.move(to: points[i].0)
                        line.addLine(to: points[j].0)
                        context.stroke(line, with: .color(tint.opacity(0.10 + max(0, (points[i].1 + points[j].1) * 0.08))), lineWidth: 0.7)
                    }
                    for (point, depth) in points {
                        let diameter: CGFloat = depth > 0 ? 3 : 1.8
                        let dot = CGRect(x: point.x - diameter/2, y: point.y - diameter/2, width: diameter, height: diameter)
                        context.fill(Path(ellipseIn: dot), with: .color(tint.opacity(depth > 0 ? 0.9 : 0.35)))
                    }
                }
            }.frame(width: 220, height: 220).accessibilityHidden(true)
            VStack {
                Spacer()
                Text(!connected ? "OFFLINE" : paused ? "PAUSED" : listening ? "LISTENING" : speaking ? "SPEAKING" : active > 0 ? "WORKING" : "READY")
                    .font(.system(size: 9, weight: .semibold, design: .monospaced)).tracking(2)
                    .foregroundStyle(tint).padding(.horizontal, 10).padding(.vertical, 5)
                    .background(HUD.ink.opacity(0.9)).clipShape(Capsule())
            }.padding(.bottom, 2)
        }.frame(width: 234, height: 234)
        .scaleEffect(expanded ? 1.48 : 1)
        .frame(width: expanded ? 350 : 234, height: expanded ? 350 : 234)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Executive core \(!connected ? "offline" : paused ? "paused" : listening ? "listening" : speaking ? "speaking" : active > 0 ? "working" : "ready")")
    }
}
struct CommandWindow: View {
    @ObservedObject var model: ExecutiveModel
    @ObservedObject var voice: VoiceController
    var selectedTask: TaskRecord? { model.tasks.first { $0.id == model.selected } }
    var active: Int { model.tasks.filter(\.active).count }
    var ready: Bool { model.connected && !model.paused && !model.submitting && !voice.recording && !voice.preparing }
    var body: some View {
        VStack(spacing: 0) {
            header
            Rectangle().fill(HUD.line).frame(height: 1)
            HStack(spacing: 0) {
                if model.showingHistory {
                    sidebar.frame(width: 242)
                    Rectangle().fill(HUD.line).frame(width: 1)
                }
                ScrollView {
                    VStack(alignment: .leading, spacing: 22) {
                        HStack {
                            VStack(alignment: .leading, spacing: 7) {
                                eyebrow("JARVIS / LOCAL")
                                Text(selectedTask == nil ? "Good to see you." : "Mission detail")
                                    .font(.system(size: 27, weight: .light))
                            }
                            Spacer()
                            Button(model.showingHistory ? "Hide history" : "History \(model.tasks.count)") { model.showingHistory.toggle() }.buttonStyle(HUDButton())
                            if selectedTask != nil { Button("Home") { model.selected = nil; model.showingHistory = false }.buttonStyle(HUDButton()) }
                        }
                        if let task = selectedTask { taskDetail(task) }
                        else { overview }
                    }.padding(28)
                }.background(GridBackdrop())
            }
            Rectangle().fill(HUD.line).frame(height: 1)
            composer
        }
        .background(HUD.ink).foregroundStyle(Color(red: 0.87, green: 0.93, blue: 0.96))
        .preferredColorScheme(.dark).tint(HUD.cyan)
        .frame(minWidth: 940, minHeight: 700)
    }
    var header: some View {
        HStack(spacing: 16) {
            ZStack {
                RoundedRectangle(cornerRadius: 9).stroke(HUD.cyan.opacity(0.6)).frame(width: 42, height: 42)
                Image(systemName: "cpu").font(.system(size: 23, weight: .light)).foregroundStyle(HUD.cyan)
            }
            VStack(alignment: .leading, spacing: 3) {
                Text("J A R V I S").font(.system(size: 21, weight: .semibold, design: .monospaced))
                eyebrow("PERSONAL EXECUTIVE SYSTEM")
            }
            Spacer()
            Circle().fill(!model.connected ? .red : model.paused ? .orange : HUD.cyan).frame(width: 6, height: 6)
            Text(model.status).font(.system(size: 11, design: .monospaced)).foregroundStyle(HUD.muted)
            Text("LOCAL").font(.system(size: 10, weight: .bold, design: .monospaced)).foregroundStyle(HUD.cyan)
                .padding(8).overlay(RoundedRectangle(cornerRadius: 4).stroke(HUD.line))
        }.padding(.horizontal, 24).padding(.vertical, 18)
    }
    var sidebar: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack { eyebrow("MISSION ARCHIVE"); Spacer(); Text(String(model.tasks.count)).font(.system(size: 11, design: .monospaced)).foregroundStyle(HUD.cyan) }
                .padding(.horizontal, 18).padding(.top, 24)
            if model.tasks.isEmpty {
                Text("No missions yet.\nYour verified history appears here.")
                    .font(.system(size: 12)).foregroundStyle(HUD.muted).padding(18)
            }
            ScrollView {
                LazyVStack(spacing: 7) {
                    ForEach(model.tasks) { task in
                        Button { model.selected = task.id } label: {
                            VStack(alignment: .leading, spacing: 9) {
                                HStack {
                                    Circle().fill(stateColor(task.state)).frame(width: 5, height: 5)
                                    Text(stateLabel(task)).font(.system(size: 9, weight: .medium, design: .monospaced)).tracking(1)
                                    Spacer()
                                    Text(String(task.id.prefix(6))).font(.system(size: 9, design: .monospaced)).foregroundStyle(HUD.muted)
                                }
                                Text(task.command).font(.system(size: 12, weight: .medium)).lineLimit(2).multilineTextAlignment(.leading)
                            }.padding(12).frame(maxWidth: .infinity, alignment: .leading)
                                .background(model.selected == task.id ? HUD.cyan.opacity(0.1) : HUD.panel.opacity(0.6))
                                .clipShape(RoundedRectangle(cornerRadius: 7))
                                .overlay(RoundedRectangle(cornerRadius: 7).stroke(model.selected == task.id ? HUD.cyan.opacity(0.4) : Color.clear))
                        }.buttonStyle(.plain).accessibilityLabel("\(task.command), \(task.state)")
                    }
                }.padding(.horizontal, 12)
            }
            VStack(alignment: .leading, spacing: 8) {
                Label("Scoped access enforced", systemImage: "lock.shield").foregroundStyle(HUD.cyan)
                Text("Every action leaves evidence.").foregroundStyle(HUD.muted)
            }.font(.system(size: 10, design: .monospaced)).padding(18)
        }.background(HUD.panel.opacity(0.45))
    }
    var overview: some View {
        VStack(spacing: 22) {
            HStack(spacing: 28) {
                CoreDisplay(connected: model.connected, paused: model.paused, active: active,
                            listening: voice.recording || voice.preparing, speaking: voice.speaking, expanded: true)
                VStack(alignment: .leading, spacing: 14) {
                    eyebrow("SYSTEM STATUS")
                    Text(model.connected ? "Standing by for your next move." : "Reconnect to your executive.")
                        .font(.system(size: 23, weight: .light)).fixedSize(horizontal: false, vertical: true)
                    Text("Ask anything, or tell me what to do.")
                        .font(.system(size: 12)).foregroundStyle(HUD.muted)
                    Text(voice.recording ? "Listening to you…" : voice.speaking ? "Speaking…" : active > 0 ? "Working on it…" : "Ready when you are.")
                        .font(.system(size: 11, design: .monospaced)).foregroundStyle(HUD.cyan)
                }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(18)
                .background(HUD.panel.opacity(0.65)).clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(HUD.line))
            HStack(spacing: 12) {
                Image(systemName: "brain").foregroundStyle(HUD.cyan)
                VStack(alignment: .leading, spacing: 4) {
                    eyebrow("LOCAL REASONING")
                    Text(model.modelInfo.map { "\($0.model) · \($0.status)" } ?? "Checking local model…")
                        .font(.system(size: 12, design: .monospaced))
                }
                Spacer()
                Text("PROPOSE → CONFIRM → EXECUTE").font(.system(size: 9, design: .monospaced)).foregroundStyle(HUD.muted)
            }.padding(16).background(HUD.panel).clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }
    func taskDetail(_ task: TaskRecord) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text(stateLabel(task)).font(.system(size: 11, weight: .semibold, design: .monospaced)).tracking(2).foregroundStyle(stateColor(task.state))
                if task.active { ProgressView().controlSize(.small) }
                Spacer()
                if task.active { Button("Cancel task") { model.action("tasks/\(task.id)/cancel") }.buttonStyle(HUDButton()).disabled(!model.connected) }
            }
            Text(task.command).font(.system(size: 24, weight: .light)).textSelection(.enabled)
            if task.state == "awaiting_approval" {
                VStack(alignment: .leading, spacing: 12) {
                    eyebrow("CONFIRM PROPOSED ACTION")
                    Text(model.capabilities.first { $0.id == task.capability }?.title ?? task.capability ?? "Unknown action")
                        .font(.system(size: 19, weight: .medium))
                    Text("Review the command and its permissions. No action has been executed.").font(.system(size: 12)).foregroundStyle(HUD.muted)
                    Text(task.approval.text + "\n" + task.scope.text).font(.system(size: 12, design: .monospaced)).textSelection(.enabled)
                    if let proposal = task.proposal { Text(proposal.reason).font(.system(size: 11, design: .monospaced)).textSelection(.enabled) }
                    HStack {
                        Button("Confirm action") { model.action("tasks/\(task.id)/approve") }.buttonStyle(HUDButton(primary: true)).disabled(!model.connected || model.paused)
                        Button("Reject") { model.action("tasks/\(task.id)/cancel") }.buttonStyle(HUDButton()).disabled(!model.connected)
                    }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(18).background(HUD.panel)
                    .clipShape(RoundedRectangle(cornerRadius: 8)).overlay(RoundedRectangle(cornerRadius: 8).stroke(HUD.cyan.opacity(0.4)))
            }
            if let error = task.error { section("ACTION REQUIRED", error, accent: .orange) }
            if let result = task.result {
                section("OUTPUT", result.text)
                HStack {
                    Button { voice.speak(result.spokenText) } label: { Label("Read result", systemImage: "speaker.wave.2") }
                        .buttonStyle(HUDButton()).disabled(voice.recording || voice.preparing)
                        .accessibilityLabel("Read selected task result aloud")
                    if voice.speaking {
                        Button("Stop speech") { voice.stopSpeaking() }.buttonStyle(HUDButton())
                    }
                }
            }
            if !task.evidence.isEmpty { section("EVIDENCE & LIMITATIONS", task.evidence.map(\.text).joined(separator: "\n\n")) }
            DisclosureGroup("Authorization & scope") { section("SCOPED GRANT", task.approval.text + "\n" + task.scope.text) }
                .font(.system(size: 11, design: .monospaced)).foregroundStyle(HUD.muted)
            VStack(alignment: .leading, spacing: 12) {
                eyebrow("EXECUTION TRACE")
                ForEach(Array(task.events.enumerated()), id: \.offset) { _, event in
                    HStack(alignment: .top, spacing: 10) {
                        Circle().fill(stateColor(event.state)).frame(width: 5, height: 5).padding(.top, 5)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(event.message).font(.system(size: 12))
                            Text(event.time).font(.system(size: 9, design: .monospaced)).foregroundStyle(HUD.muted)
                        }
                    }
                }
            }.textSelection(.enabled)
        }
    }
    var composer: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                Text(">_").font(.system(size: 19, weight: .medium, design: .monospaced)).foregroundStyle(HUD.cyan)
                TextField("Ask a question or enter a command…", text: $model.command).textFieldStyle(.plain)
                    .font(.system(size: 14, design: .monospaced))
                    .onSubmit { if ready { model.submit() } }
                    .accessibilityLabel("Command input")
                Button {
                    voice.toggleCapture { text in
                        model.command += (model.command.isEmpty ? "" : " ") + text
                    }
                } label: {
                    Label(voice.recording || voice.preparing ? "Stop mic" : "Mic", systemImage: voice.recording ? "stop.circle" : "mic")
                }.buttonStyle(HUDButton()).disabled(voice.handsFreeEnabled)
                    .accessibilityLabel(voice.recording || voice.preparing ? "Stop microphone and review transcript" : "Start on-device voice input")
                    .help("Press to start, press again to stop. Text is reviewed before execution.")
                Button { model.submit() } label: { Label("Execute", systemImage: "arrow.up.right") }
                    .buttonStyle(HUDButton(primary: true)).keyboardShortcut(.return, modifiers: .command)
                    .disabled(!ready || model.command.isEmpty).opacity(ready ? 1 : 0.4)
            }.padding(12).background(HUD.panel).clipShape(RoundedRectangle(cornerRadius: 9))
                .overlay(RoundedRectangle(cornerRadius: 9).stroke(HUD.cyan.opacity(0.35)))
            Text(voice.status).font(.system(size: 11, design: .monospaced)).foregroundStyle(HUD.cyan)
                .fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
            if voice.recording && !voice.transcript.isEmpty {
                Text(voice.transcript).font(.caption).foregroundStyle(HUD.muted).lineLimit(2)
            }
            if let error = model.error { Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled) }
            HStack(spacing: 15) {
                Button(voice.handsFreeEnabled ? "Hands-free on" : "Hands-free off") { model.toggleHandsFree() }
                    .foregroundStyle(voice.handsFreeEnabled ? HUD.cyan : HUD.muted)
                Button("Stop All") { model.action("stop-all") }.foregroundStyle(.orange)
                if model.paused { Button("Resume") { model.action("resume") }.disabled(!model.connected) }
                if !model.connected { Button("Restart Executive") { model.start() } }
                Spacer()
                Menu("More") {
                    Button("Choose notes folder") { model.chooseMemoryFolder() }.disabled(!model.connected || model.paused)
                    if model.memoryFolder?.kind == "selected" {
                        Button("Use demo notes") { model.setMemoryFolder("") }.disabled(!model.connected || model.paused)
                    }
                    if let folder = model.memoryFolder { Text("Notes: \(folder.path)") }
                    Divider()
                    Button("Quit JARVIS") { NSApplication.shared.terminate(nil) }
                }
            }.buttonStyle(.plain).font(.system(size: 11, weight: .medium, design: .monospaced))
        }.padding(.horizontal, 24).padding(.vertical, 16).background(HUD.ink)
    }
    func eyebrow(_ text: String) -> some View {
        Text(text).font(.system(size: 9, weight: .medium, design: .monospaced)).tracking(1.5).foregroundStyle(HUD.muted)
    }
    func metric(_ label: String, _ count: Int) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(String(format: "%02d", count)).font(.system(size: 23, weight: .light, design: .monospaced)).foregroundStyle(HUD.cyan)
            eyebrow(label)
        }
    }
    func section(_ title: String, _ text: String, accent: Color = HUD.cyan) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(.system(size: 9, weight: .medium, design: .monospaced)).tracking(1.5).foregroundStyle(accent)
            Text(text).font(.system(size: 12, design: .monospaced)).textSelection(.enabled)
        }.frame(maxWidth: .infinity, alignment: .leading).padding(18).background(HUD.panel)
            .clipShape(RoundedRectangle(cornerRadius: 8)).overlay(RoundedRectangle(cornerRadius: 8).stroke(accent.opacity(0.18)))
    }
    func stateLabel(_ task: TaskRecord) -> String {
        if task.state == "succeeded", task.capability == "chat.local" { return "ANSWERED" }
        return task.state.replacingOccurrences(of: "_", with: " ").uppercased()
    }

    func stateColor(_ state: String) -> Color {
        switch state { case "succeeded": return HUD.cyan; case "failed", "interrupted": return .orange; case "running", "queued", "awaiting_approval": return .yellow; default: return HUD.muted }
    }
    func icon(_ id: String) -> String {
        switch id { case "apps.calculator": return "calculator"; case "apps.finder": return "macwindow"; case "files.list": return "folder"; default: return "doc.badge.plus" }
    }
}

private final class FloatingCompanionHost: NSView {
    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        guard let window else { return }
        window.level = .floating
        window.collectionBehavior.insert(.canJoinAllSpaces)
        window.isMovableByWindowBackground = true
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
    }
}

private struct FloatingCompanionWindow: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView { FloatingCompanionHost() }
    func updateNSView(_ view: NSView, context: Context) {}
}

struct CompanionWindow: View {
    @ObservedObject var model: ExecutiveModel
    @Environment(\.openWindow) private var openWindow
    var body: some View {
        VStack(spacing: 8) {
            CoreDisplay(connected: model.connected, paused: model.paused,
                        active: model.tasks.filter(\.active).count,
                        listening: model.voice.recording || model.voice.preparing,
                        speaking: model.voice.speaking)
            HStack {
                Button("Open JARVIS") { openWindow(id: "command"); NSApp.activate(ignoringOtherApps: true) }
                Spacer()
                Button(model.voice.handsFreeEnabled ? "Listening" : "Hands-free") { model.toggleHandsFree() }
            }.font(.system(size: 11, design: .monospaced))
        }
        .padding(14)
        .frame(width: 280, height: 285)
        .background(HUD.ink)
        .foregroundStyle(HUD.cyan)
        .background(FloatingCompanionWindow())
        .preferredColorScheme(.dark)
    }
}
