# Nano Remarkable Canvas

Use your **reMarkable** tablet as a pen input for your Mac. Draw on the tablet and see strokes replayed as mouse input inside a rectangle you choose on screen—like a tiny canvas for Jamboard, Figma, or any app.

## How it works

1. **reMarkable** streams raw input events over SSH (`/dev/input/event1`).
2. **stroke-convertor** reads those events and outputs normalized stroke messages (JSON lines).
3. **receiver** shows a fullscreen overlay; you drag to select the target region, then replays strokes as mouse move/down/up in that area.

All in a simple pipeline: `ssh … | stroke-convertor | receiver`.

## macOS: Allow mouse control

The app needs permission to move the mouse and simulate clicks.

**System Settings → Privacy & Security → Accessibility**

Add your terminal (Terminal.app, iTerm, Cursor, etc.) and turn it on. The first time the app requests control, a pop-up usually appears—click **Open System Settings** to grant access.

## Quick start

- find your reMarkable IP from `Remarkable Settings > Help > Copyright`
- make sure you are connected to the same network as the reMarkable
then run: 

```bash
REMARKABLE_IP=192.168.1.89 run.sh 
```
