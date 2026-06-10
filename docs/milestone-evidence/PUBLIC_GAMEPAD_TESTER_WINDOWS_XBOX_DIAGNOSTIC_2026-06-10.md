# Public Gamepad Tester Windows Xbox Diagnostic - 2026-06-10

Status: partial public-browser diagnostic. The public Gamepad API tester page was
added and deployed, and the already-proven single-persona Xbox path still drove
Windows XInput slot 0 with deterministic reports. In the automated Chrome run
on Alex's Windows PC, however, the public tester page reported zero connected
Gamepad API devices.

This is not broad Windows compatibility, broad browser compatibility, broad
game compatibility, Xbox console compatibility, proprietary Xbox Wireless
compatibility, BLE bond persistence, physical HOTAS movement, or final
calibration evidence.

## Context

- Date/time: 2026-06-10 around 12:13 Mountain time.
- Initial repo commit for this chunk: `50baf496d54f254583554b5b2d4ae2058ebe0f39`
- Public tester implementation commit: `ac0c2c156b38c9aef1f500c9d3328638441b4002`
- Current repo commit after Web Serial follow-up: `e573d76bb85b6efcd6ed64edc4e749d43ec8971d`
- Branch: `main`
- CI after the follow-up commit:
  <https://github.com/alexoviedo/T2/actions/runs/27298682689> completed
  successfully.
- Windows host: Alex's Windows PC. Registry reported `Windows 10 Home`,
  display version `25H2`, build `26200.8655`.
- Selected serial port: `COM3`
- Public tester URL:
  <https://alexoviedo.github.io/T2/gamepad-test.html>
- Artifact root:
  `target/web-cross-platform/web_cross_platform_20260610_113446`
- Windows tester artifact:
  `target/web-cross-platform/web_cross_platform_20260610_113446/windows_public_gamepad_tester`

No firmware was flashed for this diagnostic. No physical HOTAS controls were
moved.

## Target Setup

The target was probed on `COM3`. During the initial desktop web workflow probe,
the target temporarily reported only the HooToo hub. A software reset restored
the practical RJ12 Flight Pack topology:

```text
USB_STATUS:devices=3;interfaces=2;
USB_DEVICES:id=1,vid=2109,pid=2813|id=2,vid=044f,pid=b687|id=3,vid=044f,pid=b10a
```

The active BLE path remained the explicit single-persona Xbox setup:

```text
active_persona=xbox_wireless_controller
active_variant=xbox_compatibility
identity_strategy=persona_static_random_experimental
current_address=CB:B3:AE:FA:FC:EF
address_type=static_random
```

## Public Tester Page

`web/public/gamepad-test.html` was added as a static public page. It does not
use Web Serial. It polls `navigator.getGamepads()`, supports an
`xbox-standard` profile, can be armed manually or with query parameters, and
captures evidence JSON for desktop/mobile browser runs.

The deployed page was reachable after GitHub Pages deploy:

```text
https://alexoviedo.github.io/T2/gamepad-test.html
HTTP/1.1 200 OK
Last-Modified: Wed, 10 Jun 2026 18:57:15 GMT
Content-Length: 21852
```

## Windows XInput Baseline

The witness helper launched Chrome against the public URL and drove target-side
deterministic Xbox reports through `COM3`. XInput slot 0 was connected:

```json
{
  "slot": 0,
  "connected": true,
  "return_code": 0
}
```

The deterministic sequence moved through XInput for all captured scenarios:

```text
neutral
left_stick_left
left_stick_right
left_stick_up
left_stick_down
right_stick_left
right_stick_right
left_trigger_max
right_trigger_max
button_a
button_b
hat_up
hat_right
hat_down
hat_left
```

Representative target response:

```text
BLE_ACTION:action=publish_xbox_test_report;state=Connected;persona=xbox_wireless_controller;report_id=1;bytes=ffff0080008000800000000000000000;
```

This confirms the Windows XInput path was still alive during the public tester
diagnostic. It does not prove browser Gamepad API exposure.

## Browser Gamepad API Result

Chrome was launched with a temporary profile and the public tester page was
armed by CDP mouse click. The page reported Gamepad API availability, but no
connected gamepad:

```json
{
  "has_gamepad_api": true,
  "platform": "Win32",
  "expected_profile": "xbox-standard",
  "gamepad_count": 0,
  "primary_gamepad": null,
  "sample_count": 0,
  "changed_axes": [],
  "changed_buttons": [],
  "profile_matched": false
}
```

The helper therefore classified the browser result as failed/partial:

```json
{
  "browser_pass": false,
  "browser_reasons": [
    "tester reported no connected gamepad",
    "tester did not report changed axes",
    "tester did not report changed buttons"
  ],
  "xinput_pass": true
}
```

## Conclusion

Partial diagnostic:

- Pass: public tester page exists, is deployed, and captures evidence JSON.
- Pass: the single-persona Xbox path still drove Windows XInput slot 0 with
  deterministic reports during the run.
- Fail/partial: Chrome Gamepad API on this PC reported zero connected gamepads
  for the paired Xbox BLE/XInput device in the automated public-page run.
- Not attempted: iPhone Safari and Quest Browser tester runs, because the
  Windows public browser run did not pass.

## Limitations

- This is one Windows PC and one automated Chrome run.
- XInput evidence is not browser Gamepad API evidence.
- The public tester is a browser diagnostic surface, not a real game/app
  compatibility witness.
- No physical HOTAS controls were moved.
- No iOS or Quest/Android compatibility is proven.
- No Web Serial configurator success is proven by this document.
- No broad Windows/browser/game compatibility, Xbox console/proprietary
  wireless support, BLE bond persistence, or final calibration is proven.
