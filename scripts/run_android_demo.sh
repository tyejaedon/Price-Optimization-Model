#!/usr/bin/env bash
set -euo pipefail

# Automated Live Physical-Device Demo & Test Runner (Mentor + Admin Android Apps)
# Usage:
#   ./scripts/run_android_demo.sh            # Offline demo mode (default)
#   ./scripts/run_android_demo.sh --live     # Live local FastAPI backend via adb reverse

MODE="offline"
if [[ "${1:-}" == "--live" ]]; then
  MODE="live"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN_REPO_DIR="/Users/tyejaedon/PycharmProjects/Price-Optimization-Model"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export PATH="$PATH:$ANDROID_HOME/platform-tools:/opt/homebrew/bin"

GRADLE_BIN="${GRADLE_BIN:-/Users/tyejaedon/.gradle/wrapper/dists/gradle-9.6.0-bin/42k10rwplmzkhuboz9kdazi7s/gradle-9.6.0/bin/gradle}"
if ! command -v gradle >/dev/null 2>&1 && [[ -x "$GRADLE_BIN" ]]; then
  GRADLE_CMD="$GRADLE_BIN"
else
  GRADLE_CMD="gradle"
fi

OUT_DIR="${OUT_DIR:-$ROOT_DIR/build/android-demo}"
mkdir -p "$OUT_DIR"

BACKEND_PID=""
RECORD_PID=""
cleanup() {
  if [[ -n "$RECORD_PID" ]]; then
    adb shell pkill -INT screenrecord >/dev/null 2>&1 || true
    wait "$RECORD_PID" 2>/dev/null || true
  fi
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "==> [1/6] Checking connected physical device..."
DEVICE_SERIAL="$(adb devices | awk 'NR>1 && $2=="device" {print $1; exit}')"
if [[ -z "$DEVICE_SERIAL" ]]; then
  echo "ERROR: No authorized Android device connected via adb." >&2
  exit 1
fi
echo "Connected device: $DEVICE_SERIAL"
adb shell input keyevent KEYCODE_WAKEUP || true

LIVE_FLAG="false"
GRADLE_PROPS=(-PuseLiveBackend=false)

if [[ "$MODE" == "live" ]]; then
  echo "==> [2/6] Starting local FastAPI backend & adb reverse tcp:8000..."
  LIVE_FLAG="true"
  export FIREBASE_PROJECT_ID="${FIREBASE_PROJECT_ID:-price-optimization-model}"
  export FIRESTORE_DATABASE_ID="${FIRESTORE_DATABASE_ID:-priceoptimizationmodel}"
  export PRICING_ARTIFACT_DIR="${PRICING_ARTIFACT_DIR:-$MAIN_REPO_DIR/artifacts}"
  export MLOPS_ADMIN_TOKEN="${MLOPS_ADMIN_TOKEN:-demo-admin-token}"
  export PORT="8000"

  PYTHON_BIN="${PYTHON_BIN:-$MAIN_REPO_DIR/.venv/bin/python}"
  PYTHONPATH="$ROOT_DIR" "$PYTHON_BIN" -m uvicorn src.api.hosted:app --host 127.0.0.1 --port 8000 > "$OUT_DIR/backend.log" 2>&1 &
  BACKEND_PID=$!

  for i in $(seq 1 90); do
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "Backend healthy at http://127.0.0.1:8000/health"
      break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      echo "ERROR: Backend process exited unexpectedly. See $OUT_DIR/backend.log" >&2
      tail -n 30 "$OUT_DIR/backend.log" >&2
      exit 1
    fi
    if [[ "$i" -eq 90 ]]; then
      echo "ERROR: Backend failed to start within 90s. See $OUT_DIR/backend.log" >&2
      tail -n 30 "$OUT_DIR/backend.log" >&2
      exit 1
    fi
    sleep 1
  done

  adb reverse tcp:8000 tcp:8000
  GRADLE_PROPS=(-PuseLiveBackend=true -PpricingApiBaseUrl=http://localhost:8000/)
else
  echo "==> [2/6] Running in Offline Demo Mode (FakePricingRepository & FakeAdminRepository)"
fi

echo "==> [3/6] Running unit tests and on-device Compose instrumented tests on $DEVICE_SERIAL..."
"$GRADLE_CMD" :app:testDebugUnitTest :admin-app:testDebugUnitTest \
  :app:connectedDebugAndroidTest :admin-app:connectedDebugAndroidTest \
  --console=plain

echo "==> [4/6] Installing debug APKs (useLiveBackend=$LIVE_FLAG)..."
"$GRADLE_CMD" :app:installDebug :admin-app:installDebug \
  "${GRADLE_PROPS[@]}" --console=plain

# Helper: find UI element center (x y) by exact text, substring text, or content-desc
find_node() {
  local query="$1"
  local mode="${2:-text}"
  adb shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1 || return 1
  adb shell cat /sdcard/ui.xml 2>/dev/null | tr -d '\r' | python3 -c '
import re, sys, xml.etree.ElementTree as ET
raw = sys.stdin.read()
idx = raw.find("<?xml")
if idx == -1:
    sys.exit(1)
xml_str = raw[idx:]
end_idx = xml_str.rfind("</hierarchy>")
if end_idx != -1:
    xml_str = xml_str[:end_idx + len("</hierarchy>")]
root = ET.fromstring(xml_str)
q, mode = sys.argv[1], sys.argv[2]
for node in root.iter("node"):
    text_val = node.attrib.get("text", "")
    desc_val = node.attrib.get("content-desc", "")
    if mode == "desc":
        matched = (desc_val == q)
    elif mode == "text":
        matched = (text_val == q)
    else:
        matched = (q.lower() in text_val.lower()) or (q.lower() in desc_val.lower())
    if matched:
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            print((x1 + x2) // 2, (y1 + y2) // 2)
            sys.exit(0)
sys.exit(1)
' "$query" "$mode"
}

hide_keyboard() {
  if adb shell dumpsys input_method 2>/dev/null | grep -q "mInputShown=true"; then
    adb shell input keyevent KEYCODE_BACK || true
    sleep 0.5
  fi
}

tap_node() {
  local query="$1"
  local mode="${2:-text}"
  local coords
  coords="$(find_node "$query" "$mode" || true)"
  if [[ -z "$coords" ]]; then
    echo "WARN: UI node not found ($mode='$query')"
    return 1
  fi
  adb shell input tap $coords
  sleep 1
}

type_into_node() {
  local query="$1"
  local text="$2"
  local mode="${3:-text}"
  if tap_node "$query" "$mode"; then
    local escaped="${text// /%s}"
    adb shell input text "$escaped"
    sleep 0.5
  fi
}

snap() {
  local name="$1"
  adb shell screencap -p /sdcard/demo_snap.png >/dev/null 2>&1
  adb pull /sdcard/demo_snap.png "$OUT_DIR/$name" >/dev/null 2>&1
  echo "Captured $OUT_DIR/$name"
}

echo "==> [5/6] Starting screen recording & live Mentor App demo..."
adb shell rm -f /sdcard/pricing_demo.mp4
adb shell screenrecord --time-limit 180 /sdcard/pricing_demo.mp4 >/dev/null 2>&1 &
RECORD_PID=$!

adb shell am force-stop dev.tyejaedon.pricing
adb shell am start -n dev.tyejaedon.pricing/.MainActivity
sleep 3

# Handle Firebase sign-in if in live mode and AuthenticationScreen is shown
if [[ "$MODE" == "live" ]] && find_node "Sign in to price your service" "contains" >/dev/null 2>&1; then
  DEMO_EMAIL="${DEMO_MENTOR_EMAIL:-demo.mentor.$(date +%s)@example.com}"
  DEMO_PASS="${DEMO_MENTOR_PASSWORD:-DemoPass123!}"
  if [[ -z "${DEMO_MENTOR_EMAIL:-}" ]]; then
    tap_node "Don't have an account? Create account" "text" || true
  fi
  type_into_node "Email address" "$DEMO_EMAIL" "desc" || true
  type_into_node "Password" "$DEMO_PASS" "desc" || true
  hide_keyboard
  tap_node "Create account" "text" || tap_node "Sign in" "text" || true
  sleep 4
fi

# Handle onboarding if shown
if find_node "Complete your mentor profile" "contains" >/dev/null 2>&1; then
  type_into_node "Full name" "Demo Mentor" "text" || true
  hide_keyboard
  tap_node "Save mentor profile" "text" || true
  sleep 3
fi

snap "01_mentor_quote_step1.png"
type_into_node "Service description input" "Senior Android Kotlin Compose architecture mentoring" "desc" || true
hide_keyboard
tap_node "Industry selector" "contains" || true
tap_node "Mobile Development" "text" || true
tap_node "Continue to next step" "desc" || tap_node "Continue" "text" || true
sleep 1

snap "01b_mentor_quote_step2.png"
tap_node "Your country ISO 2-letter code" "desc" || tap_node "Your country" "contains" || true
tap_node "Kenya (KE)" "text" || true
sleep 1
tap_node "Client country ISO 2-letter code" "desc" || tap_node "Client country" "contains" || true
tap_node "United States (US)" "text" || true
sleep 1
tap_node "Continue to next step" "desc" || tap_node "Continue" "text" || true
sleep 1

snap "01c_mentor_quote_step3.png"
tap_node "Calculate recommended hourly rate" "desc" || tap_node "Get Recommended Rate" "text" || true
sleep 3
adb shell input swipe 500 1600 500 800 300
sleep 1
snap "02_mentor_quote_result.png"

tap_node "Listings" "text" || true
sleep 2
snap "03_mentor_listings.png"

tap_node "History" "text" || true
sleep 2
tap_node "Accepted" "text" || true
sleep 2
snap "04_mentor_history.png"

echo "==> [6/6] Running live Admin App demo..."
adb shell am force-stop dev.tyejaedon.pricing.admin
adb shell am start -n dev.tyejaedon.pricing.admin/.AdminActivity
sleep 3

if [[ "$MODE" == "live" ]] && find_node "Administrator Token" "contains" >/dev/null 2>&1; then
  type_into_node "Administrator Token" "${MLOPS_ADMIN_TOKEN:-demo-admin-token}" "text" || true
  hide_keyboard
  tap_node "Unlock Console" "text" || true
  sleep 4
fi

snap "05_admin_overview.png"
tap_node "MLOps" "text" || true
sleep 2
snap "06_admin_mlops.png"
tap_node "Drift & Feedback" "text" || true
sleep 2
snap "07_admin_drift.png"
tap_node "Profiles & Audit" "text" || true
sleep 2
snap "08_admin_profiles.png"

echo "==> Stopping screen recording and pulling video..."
adb shell pkill -INT screenrecord >/dev/null 2>&1 || true
wait "$RECORD_PID" 2>/dev/null || true
RECORD_PID=""
sleep 2
adb pull /sdcard/pricing_demo.mp4 "$OUT_DIR/pricing_demo.mp4" || true

echo "==> Demo complete! Artifacts saved in $OUT_DIR"
ls -lh "$OUT_DIR"
