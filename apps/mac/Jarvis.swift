import SwiftUI
import AppKit

struct TaskEvent: Decodable {
    let time: String
    let state: String
    let message: String
}
struct JSONValue: Decodable {
    let text: String
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { text = "—" }
        else if let s = try? c.decode(String.self) { text = s }
        else if let b = try? c.decode(Bool.self) { text = String(b) }
        else if let n = try? c.decode(Double.self) { text = String(n) }
        else if let a = try? c.decode([JSONValue].self) { text = a.map(\.text).joined(separator: "\n") }
        else {
            let d = try c.decode([String: JSONValue].self)
            text = d.keys.sorted().map { "\($0): \(d[$0]!.text)" }.joined(separator: "\n")
        }
    }
}
struct TaskRecord: Decodable, Identifiable {
    let id: String
    let command: String
    let capability: String?
    let state: String
    let created_at: String
    let updated_at: String
    let scope: JSONValue
    let approval: JSONValue
    let events: [TaskEvent]
    let result: JSONValue?
    let error: String?
    let evidence: [JSONValue]
    var active: Bool { state == "queued" || state == "running" }
}
struct Health: Decodable { let status: String; let paused: Bool }
struct Capability: Decodable, Identifiable { let id: String; let title: String; let commands: [String] }

@MainActor
final class ExecutiveModel: ObservableObject {
    @Published var tasks: [TaskRecord] = []
    @Published var capabilities: [Capability] = []
    @Published var status = "Starting executive…"
    @Published var connected = false
    @Published var paused = false
    @Published var error: String?
    @Published var selected: String?
    @Published var command = ""
    @Published var submitting = false
    private var process: Process?
    private var input: Pipe?
    private var port: Int?
    private var token = ""
    private var polling: Task<Void, Never>?
    private var starting = false

    init() { start() }

    func start() {
        guard !starting, process?.isRunning != true else { return }
        starting = true
        error = nil
        status = "Starting executive…"
        token = UUID().uuidString + UUID().uuidString
        guard let resources = Bundle.main.resourceURL,
              let configData = try? Data(contentsOf: resources.appendingPathComponent("config.json")),
              let config = try? JSONSerialization.jsonObject(with: configData) as? [String: String],
              let python = config["python"], let root = config["root"] else {
            error = "Build configuration missing. Rebuild using scripts/build.sh."
            starting = false
            return
        }
        let child = Process()
        child.executableURL = URL(fileURLWithPath: python)
        child.arguments = [resources.appendingPathComponent("executive/server.py").path,
                           "--data", root + "/data", "--helper", resources.appendingPathComponent("verify-app").path]
        let out = Pipe(), incoming = Pipe()
        child.standardOutput = out
        child.standardInput = incoming
        child.standardError = FileHandle.standardError
        input = incoming
        process = child
        child.terminationHandler = { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                self.connected = false
                self.port = nil
                self.starting = false
                self.status = "Executive stopped"
                self.polling?.cancel()
            }
        }
        do {
            try child.run()
            try incoming.fileHandleForWriting.write(contentsOf: Data((token + "\n").utf8))
            Task { [weak self] in
                // Pipe reading is off the main actor; a startup deadline terminates a stuck child.
                let startup = await Task.detached {
                    out.fileHandleForReading.availableData
                }.value
                guard let self else { return }
                self.starting = false
                guard let object = try? JSONSerialization.jsonObject(with: startup) as? [String: Int], let port = object["port"] else {
                    self.error = "Executive did not provide a valid startup response."
                    return
                }
                self.port = port
                self.polling = Task { [weak self] in
                    while !Task.isCancelled {
                        await self?.refresh()
                        try? await Task.sleep(for: .milliseconds(700))
                    }
                }
            }
            Task { [weak self, weak child] in
                try? await Task.sleep(for: .seconds(8))
                guard let self, self.starting else { return }
                self.error = "Executive startup timed out."
                child?.terminate()
            }
        } catch {
            self.error = error.localizedDescription
            starting = false
            status = "Could not start executive"
        }
    }

    func request(_ path: String, body: [String: String]? = nil) async throws -> Data {
        guard let port else { throw URLError(.cannotConnectToHost) }
        var request = URLRequest(url: URL(string: "http://127.0.0.1:\(port)/v1/\(path)")!)
        request.timeoutInterval = 4
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let body {
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: String])?["error"] ?? "Executive request failed"
            throw NSError(domain: "JARVIS", code: 1, userInfo: [NSLocalizedDescriptionKey: detail])
        }
        return data
    }

    func refresh() async {
        do {
            let health = try JSONDecoder().decode(Health.self, from: await request("health"))
            tasks = try JSONDecoder().decode([TaskRecord].self, from: await request("tasks"))
            if capabilities.isEmpty {
                capabilities = try JSONDecoder().decode([Capability].self, from: await request("capabilities"))
            }
            connected = health.status == "ok"
            paused = health.paused
            status = paused ? "Executive paused" : "Executive connected · local only"
        } catch {
            connected = false
            status = "Executive disconnected"
        }
    }

    func submit(_ phrase: String? = nil) {
        let text = phrase ?? command
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        submitting = true
        error = nil
        Task {
            defer { submitting = false }
            do {
                let record = try JSONDecoder().decode(TaskRecord.self, from: await request("tasks", body: ["command": text]))
                command = ""
                selected = record.id
                await refresh()
            } catch { self.error = error.localizedDescription }
        }
    }

    func action(_ path: String) {
        Task {
            do { _ = try await request(path, body: [:]); await refresh() }
            catch { self.error = error.localizedDescription }
        }
    }

    func shutdown() {
        polling?.cancel()
        // EOF on the private pipe causes graceful backend stop/cancel and shutdown.
        try? input?.fileHandleForWriting.close()
        if let process, process.isRunning {
            process.terminate()
            let deadline = Date().addingTimeInterval(3)
            while process.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.05) }
        }
    }
}

struct CommandWindow: View {
    @ObservedObject var model: ExecutiveModel
    var selectedTask: TaskRecord? { model.tasks.first { $0.id == model.selected } }
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Image(systemName: "sparkle").font(.title).foregroundStyle(.blue)
                VStack(alignment: .leading) {
                    Text("JARVIS").font(.title2.bold())
                    Text("Your local executive · Phase 1").foregroundStyle(.secondary)
                }
                Spacer()
                Circle().fill(model.connected ? (model.paused ? Color.orange : Color.green) : Color.red).frame(width: 8, height: 8)
                Text(model.status).font(.caption)
            }.padding()
            Divider()
            HSplitView {
                List(selection: $model.selected) {
                    ForEach(model.tasks) { task in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(task.command).lineLimit(2)
                            Label(task.state.capitalized, systemImage: task.active ? "hourglass" : task.state == "succeeded" ? "checkmark.circle" : "circle")
                                .font(.caption).foregroundStyle(task.state == "failed" ? .red : .secondary)
                        }.padding(.vertical, 4).tag(task.id)
                    }
                }.frame(minWidth: 210, idealWidth: 245, maxWidth: 300)
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        if let task = selectedTask {
                            Text(task.command).font(.title2.bold())
                            HStack {
                                Text(task.state.uppercased()).font(.caption.bold())
                                if task.active { ProgressView().controlSize(.small) }
                                Spacer()
                                if task.active { Button("Cancel") { model.action("tasks/\(task.id)/cancel") }.disabled(!model.connected) }
                            }
                            if let error = task.error { Text(error).foregroundStyle(.red) }
                            if let result = task.result { section("Result", result.text) }
                            if !task.evidence.isEmpty { section("Verified evidence", task.evidence.map(\.text).joined(separator: "\n\n")) }
                            section("Authorization & scope", task.approval.text + "\n" + task.scope.text)
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Progress log").font(.headline)
                                ForEach(Array(task.events.enumerated()), id: \.offset) { _, event in
                                    Text("\(event.time) · \(event.message)").font(.caption).textSelection(.enabled)
                                }
                            }
                        } else {
                            Text("Ready for a real local task").font(.title2.bold())
                            Text("Choose a command below. JARVIS records its scope, executes it, and checks the outcome.")
                            Text("This first release supports four deterministic commands. Voice, models, and agents arrive in later phases.").foregroundStyle(.secondary)
                        }
                    }.frame(maxWidth: .infinity, alignment: .leading).padding(20)
                }.frame(minWidth: 370)
            }
            Divider()
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    ForEach(model.capabilities) { capability in
                        Button(capability.title) { model.submit(capability.commands[0]) }
                            .disabled(!model.connected || model.paused || model.submitting)
                    }
                }.controlSize(.small)
                HStack {
                    TextField("Type a command, e.g. open Calculator", text: $model.command).textFieldStyle(.roundedBorder)
                        .onSubmit { if model.connected && !model.paused { model.submit() } }
                    Button("Run") { model.submit() }.keyboardShortcut(.return, modifiers: .command)
                        .disabled(!model.connected || model.paused || model.submitting || model.command.isEmpty)
                }
                if let error = model.error { Text(error).font(.caption).foregroundStyle(.red).textSelection(.enabled) }
                HStack {
                    Button("Stop All", role: .destructive) { model.action("stop-all") }.disabled(!model.connected)
                    if model.paused { Button("Resume") { model.action("resume") }.disabled(!model.connected) }
                    if !model.connected { Button("Restart Executive") { model.start() } }
                    Spacer()
                    Text("No cloud connection · Workspace-scoped files").font(.caption).foregroundStyle(.secondary)
                    Button("Quit") { NSApplication.shared.terminate(nil) }
                }
            }.padding()
        }.frame(minWidth: 760, minHeight: 530)
    }
    func section(_ title: String, _ text: String) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.headline)
            Text(text).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
        }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    var model: ExecutiveModel?
    func applicationWillTerminate(_ notification: Notification) { model?.shutdown() }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
}

@main
struct JarvisApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var model = ExecutiveModel()
    var body: some Scene {
        Window("JARVIS", id: "command") {
            CommandWindow(model: model).onAppear { delegate.model = model }
        }.defaultSize(width: 900, height: 640)
        MenuBarExtra("JARVIS", systemImage: "sparkle") {
            MenuContent(model: model)
        }
    }
}
struct MenuContent: View {
    @ObservedObject var model: ExecutiveModel
    @Environment(\.openWindow) private var openWindow
    var body: some View {
        Text(model.status)
        Button("Open JARVIS") { openWindow(id: "command"); NSApp.activate(ignoringOtherApps: true) }
        Button("Stop All") { model.action("stop-all") }.disabled(!model.connected)
        if model.paused { Button("Resume") { model.action("resume") } }
        Divider()
        Button("Quit JARVIS") { NSApp.terminate(nil) }
    }
}
