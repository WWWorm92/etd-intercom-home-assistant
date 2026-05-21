# ETD Intercom для Home Assistant

<p align="center">
  <img src="custom_components/etd_intercom/brand/icon.png" width="96" alt="ETD Intercom">
</p>

<p align="center">
  <b>Кастомная интеграция Home Assistant для домофонов ETD Online</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-41BDF5?style=for-the-badge&logo=homeassistant&logoColor=white" alt="Home Assistant">
  <img src="https://img.shields.io/badge/HACS-Custom%20Repository-41BDF5?style=for-the-badge" alt="HACS">
  <img src="https://img.shields.io/badge/Video-WHEP%20%2F%20WebRTC-7B61FF?style=for-the-badge" alt="WHEP">
  <img src="https://img.shields.io/badge/Language-Russian-2EA44F?style=for-the-badge" alt="Russian">
</p>

---

## О проекте

`ETD Intercom` — это пользовательская интеграция для Home Assistant, которая позволяет подключить домофоны, калитки, ворота и камеры ETD Online к умному дому.

Интеграция умеет авторизоваться в ETD, получать список доступных домофонов, открывать двери, показывать превью камер и выводить живое видео через WHEP/WebRTC в Lovelace-карточках.

Проект рассчитан на сценарий, когда хочется не просто открыть дверь через `rest_command`, а получить нормальную интеграцию Home Assistant с сущностями, карточками, настройками и возможностью добавлять свои ID.

---

## Возможности

- Авторизация по готовому ETD access token.
- Авторизация по номеру телефона и SMS-коду.
- Автоматическая загрузка списка домофонов из ETD API.
- Ручное добавление своих ID дверей, камер, калиток и ворот.
- Создание `button`-сущностей для открытия.
- Создание `camera`-сущностей для превью.
- Извлечение `embed_link` и WHEP-ссылок из ETD.
- Живое видео через WHEP/WebRTC.
- Backend-прокси Home Assistant для WHEP, чтобы не отдавать Bearer-токен в браузер.
- Карточка одной двери: `custom:etd-intercom-card`.
- Автоматическая обзорная карточка всех дверей: `custom:etd-intercom-overview-card`.
- Автопереподключение видео.
- Задержка запуска потоков, чтобы не перегружать браузер и Raspberry Pi.
- Широкий режим отображения для панели Sections.
- Поддержка 2–3 столбцов.
- Фильтрация карточек по названиям: подъезды, калитки, ворота.
- Подготовка к интеграции входящих звонков через SIP/baresip.

---

## Установка через HACS

### 1. Добавь репозиторий

Открой Home Assistant:

```text
HACS → три точки → Custom repositories
```

Добавь репозиторий:

```text
https://github.com/WWWorm92/etd-intercom-home-assistant
```

Категория:

```text
Integration
```

Нажми:

```text
ADD
```

### 2. Установи интеграцию

```text
HACS → ETD Intercom → Download
```

После установки перезапусти Home Assistant:

```text
Настройки → Система → Перезапустить Home Assistant
```

---

## Первичная настройка

Открой:

```text
Настройки → Устройства и службы → Добавить интеграцию
```

Найди:

```text
ETD Intercom
```

Доступны два способа входа.

### Вход по токену

Можно вставить токен в любом из двух форматов:

```text
Bearer eyJ...
```

или:

```text
eyJ...
```

Интеграция сама добавит `Bearer`, если его нет.

### Вход по номеру телефона и SMS

Можно ввести номер в одном из форматов:

```text
+79817765606
79817765606
89817765606
```

Интеграция приведёт номер к формату `+7XXXXXXXXXX`, отправит SMS и попросит код подтверждения.

После успешной авторизации появятся сущности:

```text
button.etd_*_open
camera.etd_*_camera
```

---

## Lovelace-ресурс

После установки добавь JavaScript-ресурс карточки:

```text
Настройки → Панели → Ресурсы → Добавить ресурс
```

URL:

```text
/etd_intercom/etd-intercom-card.js?v=0.8.3
```

Тип:

```text
JavaScript module
```

После добавления обнови страницу браузера через `Ctrl + F5`.

---

## Быстрый старт: обзорная карточка

Самый удобный вариант — добавить одну карточку, которая сама найдёт все камеры и кнопки ETD.

```yaml
type: custom:etd-intercom-overview-card
title: Домофон
columns: 3
mobile_columns: 1
video_mode: whep
auto_start: true
auto_retry: true
retry_count: 4
retry_delay: 2500
connect_timeout: 12000
start_stagger: 900
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

Для более лёгкого режима, без запуска всех видеопотоков:

```yaml
type: custom:etd-intercom-overview-card
title: Домофон
columns: 3
mobile_columns: 1
video_mode: preview
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

---

## Карточка одной двери

```yaml
type: custom:etd-intercom-card
camera_entity: camera.etd_podiezd_2_camera
button_entity: button.etd_podiezd_2_open
title: Подъезд 2
video_mode: whep
height: 260
open_text: Открыть
```

Если прямой WHEP работает нестабильно, используй родной ETD iframe:

```yaml
type: custom:etd-intercom-card
camera_entity: camera.etd_podiezd_2_camera
button_entity: button.etd_podiezd_2_open
title: Подъезд 2
video_mode: iframe
height: 260
open_text: Открыть
```

---

## Режимы видео

| Режим | Описание |
|---|---|
| `preview` | Только JPEG-превью камеры |
| `iframe` | Родная страница ETD `webrtc-video.html` |
| `whep` | Прямое WHEP/WebRTC-видео через прокси Home Assistant |

Рекомендуемый режим для постоянной панели:

```yaml
video_mode: whep
```

Если камер много и устройство слабое:

```yaml
video_mode: preview
```

Если WHEP в конкретной сети ведёт себя нестабильно:

```yaml
video_mode: iframe
```

---

## Широкая панель в Sections view

Если карточка в Home Assistant получается слишком узкой, используй `full_width` и `max_width`.

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

Полный пример страницы:

```yaml
views:
  - title: Домофон
    path: intercom
    icon: mdi:doorbell-video
    type: sections
    max_columns: 3
    sections:
      - type: grid
        column_span: 3
        cards:
          - type: custom:etd-intercom-overview-card
            title: Домофон
            columns: 3
            mobile_columns: 1
            video_mode: whep
            auto_start: true
            auto_retry: true
            retry_count: 4
            retry_delay: 2500
            connect_timeout: 12000
            start_stagger: 900
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

---

## Фильтрация обзорной карточки

Только подъезды:

```yaml
type: custom:etd-intercom-overview-card
title: Подъезды
include: подъезд, парадная
exclude: калитка, ворота
columns: 2
mobile_columns: 1
video_mode: preview
height: 240
```

Только калитки и ворота:

```yaml
type: custom:etd-intercom-overview-card
title: Калитки и ворота
include: калитка, ворота
columns: 2
mobile_columns: 1
video_mode: whep
auto_start: true
height: 240
```

---

## Параметры обзорной карточки

| Параметр | Значение | Описание |
|---|---|---|
| `title` | строка | Заголовок |
| `columns` | число | Количество столбцов на ПК |
| `mobile_columns` | число | Количество столбцов на телефоне |
| `include` | строка | Показывать только элементы, где имя содержит указанные слова |
| `exclude` | строка | Исключить элементы, где имя содержит указанные слова |
| `video_mode` | `preview`, `iframe`, `whep` | Режим видео |
| `auto_start` | `true` / `false` | Автоматически запускать WHEP |
| `auto_retry` | `true` / `false` | Переподключать видео при ошибках |
| `retry_count` | число | Количество попыток переподключения |
| `retry_delay` | число | Пауза между попытками, мс |
| `connect_timeout` | число | Сколько ждать видео до переподключения, мс |
| `start_stagger` | число | Задержка между запуском камер, мс |
| `height` | число | Высота видео |
| `video_fit` | `cover`, `contain` | Масштабирование видео |
| `compact` | `true` / `false` | Компактный режим |
| `open_text` | строка | Текст кнопки открытия |
| `full_width` | `true` / `false` | Растянуть карточку |
| `max_width` | строка | Максимальная ширина, например `1500px` |
| `iframe_zoom` | число | Масштаб iframe-режима |

---

## Добавление своих дверей и камер

Открой:

```text
Настройки → Устройства и службы → ETD Intercom → Настроить
```

Минимальный формат:

```text
ID | Название | Иконка
```

Примеры:

```text
000270 | Подъезд 1 | mdi:door-open
001586 | Ворота 1 | mdi:gate-open
001999 | Моя камера | mdi:cctv
```

Также поддерживается короткая запись:

```text
000267=Парадная 2
```

Полный формат:

```text
ID | Название | Иконка | Preview JPEG URL | Embed link | WHEP URL
```

Пример:

```text
001999 | Тестовая камера | mdi:cctv | https://cameras-preview-server.etd-online.ru/api/cameras/preview/001999.jpg | https://etd-online.ru/webrtc-video.html?token=...&video=intercoms_6/001999&previewid=001999.jpg&sip_username=...&preview_fallback=true&is_online=true
```

Обычно достаточно короткого формата. Интеграция сама попробует собрать preview, iframe и WHEP-ссылки.

---

## Сущности

Интеграция создаёт кнопки открытия:

```text
button.etd_*_open
```

и камеры:

```text
camera.etd_*_camera
```

Примеры:

```text
button.etd_podiezd_2_open
camera.etd_podiezd_2_camera
```

---

## Атрибуты камер

У камер могут быть атрибуты:

```text
intercom_id
etd_name
preview_jpeg
camera_embed_link
camera_whep_url
camera_whep_proxy_path
```

`camera_whep_url` может содержать временный video-token. Не публикуй его в открытом доступе.

---

## Атрибуты кнопок

У кнопок открытия могут быть атрибуты последнего запроса:

```text
intercom_id
last_status_code
last_ok
last_body_raw
last_error
```

Это удобно для диагностики: можно понять, принял ли ETD команду открытия.

---

## Как работает видео

ETD отдаёт не RTSP, не HLS и не MJPEG. Видео идёт через Flussonic WHEP/WebRTC.

Пример внутренней WHEP-ссылки:

```text
https://flussonic.etd-site.ru/intercoms_6/000267/whep?token=...
```

Для подключения нужен `Authorization: Bearer ...`, поэтому интеграция использует backend-прокси Home Assistant:

```text
/api/etd_intercom/whep/{entry_id}/{intercom_id}
```

Так Bearer-токен остаётся на стороне Home Assistant и не передаётся напрямую в frontend-карточку.

---

## Входящие звонки

Открытие и видео уже работают внутри интеграции. Входящие звонки ETD идут через SIP.

В профиле ETD можно найти SIP-данные:

```text
sip_username
sip_password
transport
```

SIP-сервер:

```text
pbx.etd-online.ru:5060
```

Рекомендуемая схема для звонков:

```text
baresip
→ входящий SIP-звонок
→ MQTT
→ Home Assistant
→ уведомление + нужная камера + кнопка открытия
```

Планируется вынести это в отдельный модуль или дополнительную настройку интеграции.

---

## Обновление

Если интеграция установлена через HACS:

```text
HACS → ETD Intercom → Redownload
```

Затем:

```text
Настройки → Система → Перезапустить Home Assistant
```

Если обновлялась frontend-карточка, измени версию ресурса:

```text
/etd_intercom/etd-intercom-card.js?v=0.8.3
```

и обнови браузер через:

```text
Ctrl + F5
```

---

## Диагностика

### Карточка не отображается

Проверь ресурс:

```text
/etd_intercom/etd-intercom-card.js?v=0.8.3
```

Тип должен быть:

```text
JavaScript module
```

После изменения ресурса сделай `Ctrl + F5`.

### Видео не стартует

Попробуй:

```yaml
video_mode: iframe
```

Если iframe работает, а WHEP нет — проблема в WebRTC/WHEP-подключении, а не в доступе к камере.

### Видео появляется не всегда

Увеличь таймауты:

```yaml
auto_retry: true
retry_count: 5
retry_delay: 3000
connect_timeout: 15000
start_stagger: 1200
```

### Карточка узкая

Добавь:

```yaml
full_width: true
max_width: 1500px
grid_options:
  columns: 12
  rows: auto
```

---

## Безопасность

Не публикуй в GitHub:

```text
access_token
Authorization Bearer token
sip_password
номер телефона
адрес
flat_id
user_id
device_id
camera_whep_url с реальным token
```

Все секретные данные должны храниться только локально в Home Assistant или на устройстве, где работает SIP-клиент.

---

## Известные ограничения

- ETD не отдаёт обычный RTSP/HLS/MJPEG-поток.
- Видео работает через WHEP/WebRTC.
- При большом количестве камер одновременный запуск всех потоков может нагружать браузер.
- Для слабых устройств лучше использовать `preview` или увеличивать `start_stagger`.
- Входящие звонки требуют отдельной SIP-настройки.
- Для ворот с двумя кнопками вызова могут существовать разные видеоканалы. Их нужно добавлять как отдельные кастомные камеры.

---

## Планы

- MQTT-мост для входящих звонков через `baresip`.
- Уведомления Home Assistant при вызове.
- Автоматическое открытие нужной камеры при звонке.
- Поддержка двух камер для ворот: внутренняя и наружная.
- Улучшенная диагностика ETD API.
- Импорт и экспорт пользовательских ID.
- Страница диагностики интеграции.
- Автоматическое обновление списка устройств.
- Улучшенная поддержка go2rtc.

---

## История версий

### v0.8.3

- Добавлены `full_width` и `max_width`.
- Улучшено отображение обзорной карточки в Sections view.

### v0.8.2

- Добавлено автопереподключение WHEP.
- Добавлен последовательный запуск потоков через `start_stagger`.

### v0.8.1

- Улучшено широкое отображение камер.
- Добавлены `video_fit`, `compact`, `iframe_zoom`.

### v0.8.0

- Добавлена обзорная карточка `custom:etd-intercom-overview-card`.

### v0.7.4

- Исправлена сборка WHEP-ссылок для кастомных ID.

### v0.7.3

- Убрана нижняя подпись из карточки по умолчанию.

### v0.7.2

- Исправлен options flow.

### v0.7.1

- Исправлен overlay `Ожидание видео...` после старта потока.

### v0.7.0

- Добавлен WHEP-прокси и прямой WHEP-режим.

---

## Лицензия

Проект является пользовательской интеграцией для Home Assistant.

Используй интеграцию только для тех домофонов и камер ETD, к которым у тебя есть законный доступ.
