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
struct ProposalInfo: Decodable { let capability: String; let reason: String }
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
    let proposal: ProposalInfo?
    var active: Bool { state == "queued" || state == "running" }
}
struct Health: Decodable { let status: String; let paused: Bool }
struct ModelInfo: Decodable { let model: String; let status: String; let installed: Bool; let available: Bool; let enabled: Bool }
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
    @Published var modelInfo: ModelInfo?
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
            modelInfo = try? JSONDecoder().decode(ModelInfo.self, from: await request("model"))
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
        }.defaultSize(width: 1120, height: 780)
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
