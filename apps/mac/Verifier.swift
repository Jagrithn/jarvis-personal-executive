import AppKit
import Foundation
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
