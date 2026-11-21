import AppKit
import Foundation
import PDFKit
if CommandLine.arguments.count == 2, CommandLine.arguments[1] == "--extract-pdf" {
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard let document = PDFDocument(data: data), !document.isLocked,
          document.pageCount <= 500, let text = document.string, !text.isEmpty else {
        fputs("PDF is invalid, locked, too long, or contains no selectable text\n", stderr)
        exit(1)
    }
    guard text.utf8.count <= 2_000_000 else {
        fputs("Extracted PDF text exceeds the limit\n", stderr)
        exit(1)
    }
    print(text, terminator: "")
    exit(0)
}
if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--chrome-search" {
    guard let url = URL(string: CommandLine.arguments[2]), url.scheme == "https", url.host == "www.google.com", url.path == "/search",
          let chrome = NSWorkspace.shared.urlForApplication(withBundleIdentifier: "com.google.Chrome") else {
        fputs("Chrome or the search URL is unavailable\n", stderr); exit(1)
    }
    NSWorkspace.shared.open([url], withApplicationAt: chrome, configuration: NSWorkspace.OpenConfiguration()) { app, error in
        guard error == nil, let id = app?.bundleIdentifier else { exit(1) }
        print(id); exit(0)
    }
    RunLoop.main.run()
}
if CommandLine.arguments.count == 3, CommandLine.arguments[1] == "--open-item" {
    let url = URL(fileURLWithPath: CommandLine.arguments[2])
    NSWorkspace.shared.open(url, configuration: NSWorkspace.OpenConfiguration()) { app, error in
        if let app, error == nil {
            print(app.bundleIdentifier ?? app.localizedName ?? "macOS handler")
            exit(0)
        }
        fputs((error?.localizedDescription ?? "macOS could not open the item") + "\n", stderr)
        exit(1)
    }
    RunLoop.main.run()
}
let bundle = CommandLine.arguments.dropFirst().first ?? ""
let allowed = ["com.apple.calculator", "com.apple.finder"]
guard allowed.contains(bundle) else { exit(2) }
for _ in 0..<30 {
    if NSWorkspace.shared.runningApplications.contains(where: { $0.bundleIdentifier == bundle }) {
        print(bundle)
        exit(0)
    }
    Thread.sleep(forTimeInterval: 0.1)
}
fputs("Application not observed running\n", stderr)
exit(1)
