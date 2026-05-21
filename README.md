# ETD Intercom v0.2 для Home Assistant

Что умеет:
- вход по готовому токену;
- вход по номеру телефона + SMS;
- загрузка доступных домофонов из `/api/v1/intercom/list`;
- объединение списка из API с ручным fallback-списком калиток, ворот и подъездов;
- создание `button`-сущностей для открытия.

Установка:
1. Скопируй папку `custom_components/etd_intercom` в `/config/custom_components/etd_intercom`.
2. Перезапусти Home Assistant.
3. Открой: Настройки -> Устройства и службы -> Добавить интеграцию.
4. Найди `ETD Intercom`.
5. Выбери вход по токену или по номеру + SMS.

После настройки появятся сущности вида:
- `button.etd_kalitka_1_open`
- `button.etd_vorota_1_open`
- `button.etd_podiezd_2_open`

После нажатия кнопки смотри атрибуты сущности:
- `last_status_code`
- `last_ok`
- `last_body_raw`
- `last_error`

Важно: `camera.embed_link` из API специально не выводится в атрибуты сущности, потому что в ссылке есть video token.
