#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
ROOT="$PWD"
BUILD="$ROOT/.build"
APP="$BUILD/JARVIS.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$BUILD/module-cache"
export CLANG_MODULE_CACHE_PATH="$BUILD/module-cache"
xcrun swiftc -module-cache-path "$BUILD/module-cache" -parse-as-library apps/mac/Jarvis.swift apps/mac/CommandCenter.swift -o "$APP/Contents/MacOS/JARVIS" -framework SwiftUI -framework AppKit
xcrun swiftc -module-cache-path "$BUILD/module-cache" apps/mac/Verifier.swift -o "$APP/Contents/Resources/verify-app" -framework AppKit
cp -R services/executive "$APP/Contents/Resources/"
python3 - "$APP" "$ROOT" "$(command -v python3)" <<'PY'
import json, pathlib, plistlib, sys
app, root, python = sys.argv[1:]
path = pathlib.Path(app) / 'Contents'
(path / 'Resources/config.json').write_text(json.dumps({'root': root, 'python': python}))
with (path / 'Info.plist').open('wb') as f:
    plistlib.dump({'CFBundleExecutable': 'JARVIS', 'CFBundleIdentifier': 'local.jarvis.executive',
                  'CFBundleName': 'JARVIS', 'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1',
                  'CFBundleShortVersionString': '0.1.0', 'LSMinimumSystemVersion': '14.0',
                  'NSHighResolutionCapable': True}, f)
PY
codesign --force --deep --sign - "$APP"
print "Built $APP"
