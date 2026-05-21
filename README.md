# ETD Intercom

Интеграция Home Assistant для домофонов ETD Online.

![HACS](https://img.shields.io/badge/HACS-Custom-orange)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Integration-41BDF5)
![Video](https://img.shields.io/badge/Video-WHEP%20%2F%20WebRTC-blue)

## Возможности

- вход по токену или SMS;
- открытие дверей, калиток, ворот;
- камеры ETD в Home Assistant;
- живое видео через WHEP/WebRTC;
- ручное добавление своих ID;
- готовые Lovelace-карточки.

## Установка

Добавить в HACS как custom repository:

```text
https://github.com/WWWorm92/etd-intercom-home-assistant
```

Тип:

```text
Integration
```

После установки перезапустить Home Assistant.

## Настройка

```text
Настройки → Устройства и службы → Добавить интеграцию → ETD Intercom
```

Вход:

```text
по токену
или
по телефону + SMS
```

## Ресурс Lovelace

```text
/etd_intercom/etd-intercom-card.js?v=0.8.3
```

Тип:

```text
JavaScript module
```

## Общая карточка

```yaml
type: custom:etd-intercom-overview-card
title: Домофон
columns: 3
mobile_columns: 1
video_mode: whep
auto_start: true
auto_retry: true
height: 220
video_fit: cover
compact: true
open_text: Открыть
full_width: true
max_width: 1500px
grid_options:
  columns: 12
  rows: auto
```

## Одна камера

```yaml
type: custom:etd-intercom-card
camera_entity: camera.etd_podiezd_2_camera
button_entity: button.etd_podiezd_2_open
title: Подъезд 2
video_mode: whep
height: 260
open_text: Открыть
```

## Свои ID

```text
Настройки → Устройства и службы → ETD Intercom → Настроить
```

Формат:

```text
000270 | Подъезд 1 | mdi:door-open
001586 | Ворота 1 | mdi:gate-open
```

## Режимы видео

```text
preview — превью
iframe  — ETD-плеер
whep    — прямой WebRTC через HA proxy
```

## Важно

Не публикуйте токены, SIP-пароли, адреса и реальные WHEP-ссылки.

## Планы

- звонки через baresip/MQTT;
- уведомления в Home Assistant;
- выбор камеры при вызове.
