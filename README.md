# ETD Intercom for Home Assistant

Custom Home Assistant integration for ETD Online intercoms.

Features:

- Authorization by access token.
- Authorization by phone number and SMS.
- Loads intercom list from ETD API.
- Supports manually added intercom IDs.
- Creates `button` entities for opening doors/gates.
- Creates `camera` preview entities.
- Extracts ETD/Flussonic WHEP URLs from `embed_link`.
- Provides `custom:etd-intercom-card` for Lovelace dashboards:
  - `video_mode: iframe` — stable live view through ETD `webrtc-video.html`.
  - `video_mode: whep` — experimental direct WHEP playback through Home Assistant proxy.
  - `video_mode: preview` — preview JPEG only.

## Lovelace resource

After installing and restarting Home Assistant, add a JavaScript module resource:

```text
/etd_intercom/etd-intercom-card.js?v=0.7.3
```

## Recommended card: iframe mode

```yaml
type: custom:etd-intercom-card
camera_entity: camera.etd_podiezd_2_camera
button_entity: button.etd_podiezd_2_open
title: Подъезд 2
video_mode: iframe
height: 260
```

## Experimental direct WHEP mode

```yaml
type: custom:etd-intercom-card
camera_entity: camera.etd_podiezd_2_camera
button_entity: button.etd_podiezd_2_open
title: Подъезд 2
video_mode: whep
height: 260
```

WHEP mode uses this backend proxy:

```text
/api/etd_intercom/whep/{entry_id}/{intercom_id}
```

The proxy adds ETD `Authorization: Bearer ...` server-side, so the frontend card does not need to expose the ETD access token.

## Camera attributes

Each `camera.etd_*` entity exposes:

```text
intercom_id
etd_name
preview_jpeg
camera_embed_link
camera_whep_url
camera_whep_proxy_path
```

`camera_whep_url` may contain a temporary ETD video token. Treat it as sensitive.

## Manual IDs format

Use integration options to add manual IDs:

```text
000270 | Подъезд 1 | mdi:door-open
001586 | Ворота 1 | mdi:gate-open
```

Also supported:

```text
000267=Парадная 2
```

Full format:

```text
ID | Name | Icon | Preview JPEG URL | Embed link | WHEP URL
```

## go2rtc note

ETD video is WHEP/WebRTC from Flussonic, not RTSP/HLS/MJPEG. If direct WHEP mode is unstable in the browser, use `video_mode: iframe` or test WHEP through go2rtc manually.

A source will look roughly like this, but exact header syntax depends on your go2rtc version:

```yaml
streams:
  etd_podiezd_2:
    - webrtc:https://flussonic.etd-site.ru/intercoms_6/000267/whep?token=VIDEO_TOKEN#headers=Authorization: Bearer ACCESS_TOKEN
```


## 0.7.3
- Убрана нижняя подпись/подсказка из карточки по умолчанию.
- Для возврата подсказки можно указать `show_hint: true`.

## 0.7.2

- Fixed WHEP overlay remaining visible after video starts.

## Auto dashboard card

Since v0.8.2 you can add one overview card instead of manually adding every door/camera.

Recommended safe mode, previews only:

```yaml
type: custom:etd-intercom-overview-card
title: Домофон
columns: 2
mobile_columns: 1
video_mode: preview
height: 220
open_text: Открыть
```

Live mode via WHEP for all cards:

```yaml
type: custom:etd-intercom-overview-card
title: Домофон
columns: 2
mobile_columns: 1
video_mode: whep
auto_start: true
height: 220
open_text: Открыть
```

Filtered examples:

```yaml
type: custom:etd-intercom-overview-card
title: Подъезды
include: подъезд, парадная
exclude: калитка, ворота
video_mode: preview
```

```yaml
type: custom:etd-intercom-overview-card
title: Калитки и ворота
include: калитка, ворота
video_mode: iframe
```


## Wide overview example

```yaml
type: custom:etd-intercom-overview-card
title: Домофон
columns: 2
mobile_columns: 1
video_mode: whep
auto_start: true
height: 250
video_fit: cover
compact: true
open_text: Открыть
```

For iframe mode you can slightly crop the ETD player side bars:

```yaml
video_mode: iframe
iframe_zoom: 1.12
```
