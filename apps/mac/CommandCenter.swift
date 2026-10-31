import SwiftUI
import AppKit

private enum HUD {
    static let cyan = Color(red: 0.25, green: 0.88, blue: 0.96)
    static let ink = Color(red: 0.025, green: 0.045, blue: 0.075)
    static let panel = Color(red: 0.045, green: 0.075, blue: 0.115)
    static let muted = Color(red: 0.49, green: 0.61, blue: 0.70)
    static let line = cyan.opacity(0.17)
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
    var tint: Color { !connected ? .red : paused ? .orange : HUD.cyan }
    var body: some View {
        ZStack {
            Circle().fill(tint.opacity(0.045)).frame(width: 210, height: 210)
            Circle().stroke(tint.opacity(0.16), lineWidth: 1).frame(width: 210, height: 210)
            Circle().stroke(tint.opacity(0.3), style: StrokeStyle(lineWidth: 4, dash: [1, 11])).frame(width: 192, height: 192)
            Circle().trim(from: 0.04, to: 0.44).stroke(tint, style: StrokeStyle(lineWidth: 2, lineCap: .round)).frame(width: 166, height: 166).rotationEffect(.degrees(-90))
            Circle().trim(from: 0.54, to: 0.94).stroke(tint.opacity(0.5), style: StrokeStyle(lineWidth: 2, lineCap: .round)).frame(width: 166, height: 166).rotationEffect(.degrees(-90))
            Circle().stroke(tint.opacity(0.12), lineWidth: 14).frame(width: 139, height: 139)
            VStack(spacing: 8) {
                Image(systemName: connected ? "waveform.path" : "bolt.slash").font(.system(size: 27, weight: .light))
                Text(!connected ? "OFFLINE" : paused ? "PAUSED" : active > 0 ? "WORKING" : "READY")
                    .font(.system(size: 18, weight: .medium, design: .monospaced)).tracking(3)
                Text("EXECUTIVE CORE").font(.system(size: 8, design: .monospaced)).tracking(2)
            }.foregroundStyle(tint)
        }.frame(width: 220, height: 220)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Executive core \(!connected ? "offline" : paused ? "paused" : active > 0 ? "working" : "ready")")
    }
}
struct CommandWindow: View {
    @ObservedObject var model: ExecutiveModel
    var selectedTask: TaskRecord? { model.tasks.first { $0.id == model.selected } }
    var active: Int { model.tasks.filter(\.active).count }
    var ready: Bool { model.connected && !model.paused && !model.submitting }
    var body: some View {
        VStack(spacing: 0) {
            header
            Rectangle().fill(HUD.line).frame(height: 1)
            HStack(spacing: 0) {
                sidebar.frame(width: 242)
                Rectangle().fill(HUD.line).frame(width: 1)
                ScrollView {
                    VStack(alignment: .leading, spacing: 22) {
                        HStack {
                            VStack(alignment: .leading, spacing: 7) {
                                eyebrow("OPERATIONS / LOCAL EXECUTIVE")
                                Text(selectedTask == nil ? "Command center" : "Mission detail")
                                    .font(.system(size: 27, weight: .light))
                            }
                            Spacer()
                            Button("Overview") { model.selected = nil }.buttonStyle(HUDButton())
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
                                    Text(task.state.replacingOccurrences(of: "_", with: " ").uppercased()).font(.system(size: 9, weight: .medium, design: .monospaced)).tracking(1)
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
                CoreDisplay(connected: model.connected, paused: model.paused, active: active)
                VStack(alignment: .leading, spacing: 14) {
                    eyebrow("SYSTEM STATUS")
                    Text(model.connected ? "Standing by for your next move." : "Reconnect to your executive.")
                        .font(.system(size: 23, weight: .light)).fixedSize(horizontal: false, vertical: true)
                    Text("Give a command. Track the execution. Inspect the proof.")
                        .font(.system(size: 12)).foregroundStyle(HUD.muted)
                    HStack(spacing: 20) {
                        metric("ACTIVE", active)
                        metric("VERIFIED", model.tasks.filter { $0.state == "succeeded" }.count)
                        metric("CAPABILITIES", model.capabilities.count)
                    }.padding(.top, 4)
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
            VStack(alignment: .leading, spacing: 12) {
                eyebrow("QUICK OPERATIONS")
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                    ForEach(model.capabilities) { cap in
                        Button { model.submit(cap.commands[0]) } label: {
                            HStack(spacing: 12) {
                                Image(systemName: icon(cap.id)).font(.system(size: 19, weight: .light)).foregroundStyle(HUD.cyan).frame(width: 25)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(cap.title).font(.system(size: 13, weight: .medium))
                                    Text(cap.id.hasPrefix("apps") ? "APP CONTROL" : "WORKSPACE").font(.system(size: 8, design: .monospaced)).tracking(1).foregroundStyle(HUD.muted)
                                }
                                Spacer()
                                Image(systemName: "arrow.up.right").font(.system(size: 11)).foregroundStyle(HUD.cyan)
                            }.padding(16).background(HUD.panel).clipShape(RoundedRectangle(cornerRadius: 8))
                                .overlay(RoundedRectangle(cornerRadius: 8).stroke(HUD.line))
                        }.buttonStyle(.plain).disabled(!ready).opacity(ready ? 1 : 0.4)
                    }
                }
            }
        }
    }
    func taskDetail(_ task: TaskRecord) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Text(task.state.replacingOccurrences(of: "_", with: " ").uppercased()).font(.system(size: 11, weight: .semibold, design: .monospaced)).tracking(2).foregroundStyle(stateColor(task.state))
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
                    Text("Review this interpretation. No action has been executed.").font(.system(size: 12)).foregroundStyle(HUD.muted)
                    if let proposal = task.proposal { Text(proposal.reason).font(.system(size: 11, design: .monospaced)).textSelection(.enabled) }
                    HStack {
                        Button("Confirm action") { model.action("tasks/\(task.id)/approve") }.buttonStyle(HUDButton(primary: true)).disabled(!model.connected || model.paused)
                        Button("Reject") { model.action("tasks/\(task.id)/cancel") }.buttonStyle(HUDButton()).disabled(!model.connected)
                    }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(18).background(HUD.panel)
                    .clipShape(RoundedRectangle(cornerRadius: 8)).overlay(RoundedRectangle(cornerRadius: 8).stroke(HUD.cyan.opacity(0.4)))
            }
            if let error = task.error { section("ACTION REQUIRED", error, accent: .orange) }
            if let result = task.result { section("OUTPUT", result.text) }
            if !task.evidence.isEmpty { section("VERIFIED EVIDENCE", task.evidence.map(\.text).joined(separator: "\n\n")) }
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
                TextField("Enter a command…", text: $model.command).textFieldStyle(.plain)
                    .font(.system(size: 14, design: .monospaced))
                    .onSubmit { if ready { model.submit() } }
                    .accessibilityLabel("Command input")
                Button { model.submit() } label: { Label("Execute", systemImage: "arrow.up.right") }
                    .buttonStyle(HUDButton(primary: true)).keyboardShortcut(.return, modifiers: .command)
                    .disabled(!ready || model.command.isEmpty).opacity(ready ? 1 : 0.4)
            }.padding(12).background(HUD.panel).clipShape(RoundedRectangle(cornerRadius: 9))
                .overlay(RoundedRectangle(cornerRadius: 9).stroke(HUD.cyan.opacity(0.35)))
            if let error = model.error { Text(error).font(.caption).foregroundStyle(.orange).textSelection(.enabled) }
            HStack(spacing: 15) {
                Button("Stop All") { model.action("stop-all") }.foregroundStyle(.orange).disabled(!model.connected)
                if model.paused { Button("Resume") { model.action("resume") }.disabled(!model.connected) }
                if !model.connected { Button("Restart Executive") { model.start() } }
                Spacer()
                Text("LOCAL EXECUTION  /  VERIFIED OUTCOMES").font(.system(size: 9, design: .monospaced)).tracking(1).foregroundStyle(HUD.muted)
                Button("Quit") { NSApplication.shared.terminate(nil) }
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
    func stateColor(_ state: String) -> Color {
        switch state { case "succeeded": return HUD.cyan; case "failed", "interrupted": return .orange; case "running", "queued", "awaiting_approval": return .yellow; default: return HUD.muted }
    }
    func icon(_ id: String) -> String {
        switch id { case "apps.calculator": return "calculator"; case "apps.finder": return "macwindow"; case "files.list": return "folder"; default: return "doc.badge.plus" }
    }
}
