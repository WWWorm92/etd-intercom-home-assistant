class ETDIntercomCard extends HTMLElement {
  setConfig(config) {
    if (!config.camera_entity && !config.camera) {
      throw new Error("camera_entity is required");
    }

    this.config = {
      title: config.title || null,
      camera_entity: config.camera_entity || config.camera,
      button_entity: config.button_entity || config.button || config.entity || null,
      height: config.height || 260,
      open_text: config.open_text || "Открыть",
      video_mode: config.video_mode || "iframe", // iframe | whep | preview
      video_fit: config.video_fit || "cover", // cover | contain | fill
      iframe_zoom: Number(config.iframe_zoom || 1),
      compact: config.compact === true,
      auto_start: config.auto_start !== false,
      auto_start_delay: Number(config.auto_start_delay || 0),
      auto_retry: config.auto_retry !== false,
      retry_count: Number(config.retry_count || 3),
      retry_delay: Number(config.retry_delay || 2500),
      connect_timeout: Number(config.connect_timeout || 10000),
      show_preview_if_no_video: config.show_preview_if_no_video !== false,
      show_status: config.show_status !== false,
      show_hint: config.show_hint === true,
      ...config,
    };

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    this._pc = null;
    this._whepKey = null;
    this._whepStarting = false;
    this._whepStatus = "";
    this._lastRenderKey = null;
    this._whepRetryAttempt = 0;
    this._whepTimeoutTimer = null;
    this._whepRetryTimer = null;
    this._whepAutostartTimer = null;
    this._whepConnected = false;
  }

  set hass(hass) {
    this._hass = hass;
    const key = this._buildRenderKey();
    if (key !== this._lastRenderKey || !this.shadowRoot?.hasChildNodes()) {
      this.render(true);
      this._lastRenderKey = key;
    } else {
      this._updateStatusOnly();
    }
  }

  disconnectedCallback() {
    this._stopWhep();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return {
      rows: 5,
      columns: 12,
      min_rows: 4,
      max_rows: 8,
      min_columns: 6,
      max_columns: 12,
    };
  }

  _buildRenderKey() {
    const cameraState = this._getCameraState();
    return JSON.stringify({
      camera: this.config.camera_entity,
      button: this.config.button_entity,
      title: this.config.title,
      height: this.config.height,
      mode: this.config.video_mode,
      auto_retry: this.config.auto_retry,
      retry_count: this.config.retry_count,
      connect_timeout: this.config.connect_timeout,
      embed: this._getEmbedLink(cameraState),
      whep: this._getWhepProxyPath(cameraState),
    });
  }

  _getCameraState() {
    if (!this._hass || !this.config.camera_entity) return null;
    return this._hass.states[this.config.camera_entity] || null;
  }

  _getButtonState() {
    if (!this._hass || !this.config.button_entity) return null;
    return this._hass.states[this.config.button_entity] || null;
  }

  _getTitle(cameraState) {
  if (this.config.title) return this.config.title;
  return cameraState?.attributes?.friendly_name || cameraState?.attributes?.etd_name || "ETD Intercom";
}

  _getEmbedLink(cameraState) {
    return cameraState?.attributes?.camera_embed_link || cameraState?.attributes?.embed_link || null;
  }

  _getWhepProxyPath(cameraState) {
    return cameraState?.attributes?.camera_whep_proxy_path || null;
  }

  _getPreviewUrl(cameraState) {
    if (!cameraState) return null;
    if (cameraState.attributes?.entity_picture) {
      return cameraState.attributes.entity_picture;
    }
    return `/api/camera_proxy/${this.config.camera_entity}?t=${Date.now()}`;
  }

  _openDoor() {
    if (!this._hass || !this.config.button_entity) return;
    this._hass.callService("button", "press", {
      entity_id: this.config.button_entity,
    });
  }

  _refresh() {
    if (this.config.video_mode === "whep") {
      this._whepRetryAttempt = 0;
      this._restartWhep();
      return;
    }
    this.render(true);
  }

  _lastStatus(buttonState) {
    if (!buttonState) return "";
    const attrs = buttonState.attributes || {};
    if (attrs.last_status_code === undefined && attrs.last_ok === undefined && !attrs.last_error) return "";

    if (attrs.last_error) {
      return `Ошибка: ${attrs.last_error}`;
    }

    const ok = attrs.last_ok === true ? "OK" : attrs.last_ok === false ? "FAIL" : "";
    const status = attrs.last_status_code !== undefined ? attrs.last_status_code : "";
    return [ok, status].filter(Boolean).join(" · ");
  }

  _updateStatusOnly() {
    const buttonState = this._getButtonState();
    const status = this._lastStatus(buttonState);
    const statusEl = this.shadowRoot?.querySelector(".status");
    if (statusEl) statusEl.textContent = status || "";
  }

  render(forceRefresh = false) {
    if (!this.shadowRoot || !this.config || !this._hass) return;

    const cameraState = this._getCameraState();
    const buttonState = this._getButtonState();
    const title = this._getTitle(cameraState);
    const embedLink = this._getEmbedLink(cameraState);
    const whepProxyPath = this._getWhepProxyPath(cameraState);
    const previewUrl = this._getPreviewUrl(cameraState);
    const status = this._lastStatus(buttonState);
    const height = Number(this.config.height) || 260;
    const mode = String(this.config.video_mode || "iframe").toLowerCase();
    const videoFit = ["cover", "contain", "fill", "scale-down"].includes(String(this.config.video_fit).toLowerCase())
      ? String(this.config.video_fit).toLowerCase()
      : "cover";
    const iframeZoom = Math.max(1, Number(this.config.iframe_zoom || 1));
    const compact = this.config.compact === true;

    let videoBlock = "";
    let hint = "";

    if (mode === "whep" && whepProxyPath) {
      videoBlock = `
        <div class="whep-wrap">
          <video id="whep-video" class="video" autoplay muted playsinline></video>
          <div id="whep-overlay" class="overlay">Подключение WHEP...</div>
        </div>`;
      hint = `WHEP через HA proxy. Если не подключается — переключи video_mode на iframe.`;
    } else if (mode !== "preview" && embedLink) {
      videoBlock = `<div class="iframe-shell" style="--iframe-zoom:${iframeZoom}"><iframe class="video iframe-video" src="${this._escape(embedLink)}" allow="autoplay; fullscreen; microphone; camera" referrerpolicy="no-referrer-when-downgrade"></iframe></div>`;
      hint = `Живое видео через ETD iframe.`;
    } else if (this.config.show_preview_if_no_video && previewUrl) {
      videoBlock = `<img class="video" src="${this._escape(previewUrl)}${forceRefresh ? (previewUrl.includes('?') ? '&' : '?') + 'refresh=' + Date.now() : ''}" alt="${this._escape(title)}">`;
      hint = `Показано превью.`;
    } else {
      videoBlock = `<div class="no-video">Нет ссылки на камеру. Проверь атрибуты camera_embed_link / camera_whep_proxy_path.</div>`;
      hint = `Нет видео.`;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          overflow: hidden;
          border-radius: 24px;
          background: rgba(35, 40, 55, 0.55);
          border: 1px solid rgba(255,255,255,0.08);
          box-shadow: 0 8px 30px rgba(0,0,0,0.25);
          backdrop-filter: blur(18px);
        }
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: ${compact ? "10px 14px 8px" : "14px 16px 10px"};
        }
        .title {
          font-size: 16px;
          font-weight: 650;
          line-height: 1.25;
          color: var(--primary-text-color);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .status {
          font-size: 12px;
          opacity: 0.72;
          white-space: nowrap;
          color: var(--secondary-text-color);
        }
        .body {
          height: ${height}px;
          background: rgba(0,0,0,0.25);
          overflow: hidden;
          position: relative;
        }
        .video {
          width: 100%;
          height: 100%;
          border: 0;
          display: block;
          object-fit: ${videoFit};
          background: #000;
        }
        .iframe-shell {
          width: 100%;
          height: 100%;
          position: relative;
          overflow: hidden;
          background: #000;
        }
        .iframe-video {
          position: absolute;
          top: 50%;
          left: 50%;
          width: calc(100% / var(--iframe-zoom));
          height: calc(100% / var(--iframe-zoom));
          transform: translate(-50%, -50%) scale(var(--iframe-zoom));
          transform-origin: center center;
        }
        .whep-wrap { width: 100%; height: 100%; position: relative; background: #000; }
        .overlay {
          position: absolute;
          left: 12px;
          bottom: 12px;
          right: 12px;
          padding: 8px 10px;
          border-radius: 12px;
          background: rgba(0,0,0,.55);
          color: white;
          font-size: 12px;
          text-align: center;
          pointer-events: none;
        }
        .overlay.hidden { display: none; }
        .no-video {
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          text-align: center;
          padding: 16px;
          color: var(--secondary-text-color);
          box-sizing: border-box;
        }
        .actions {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 10px;
          padding: ${compact ? "8px 10px 10px" : "12px"};
        }
        button {
          border: 1px solid rgba(76,175,80,0.45);
          background: rgba(20, 90, 45, 0.42);
          color: var(--primary-text-color);
          border-radius: 18px;
          padding: ${compact ? "11px 14px" : "13px 16px"};
          font-size: 15px;
          font-weight: 650;
          cursor: pointer;
          transition: transform 0.08s ease, background 0.15s ease;
        }
        button:active { transform: scale(0.98); }
        button:disabled {
          opacity: 0.45;
          cursor: not-allowed;
        }
        .refresh {
          width: 48px;
          padding: 0;
          border-color: rgba(255,255,255,0.12);
          background: rgba(255,255,255,0.06);
        }
        .hint {
          padding: 0 14px 12px;
          font-size: 12px;
          opacity: .65;
          color: var(--secondary-text-color);
        }
      </style>
      <ha-card>
        <div class="header">
          <div class="title">${this._escape(title)}</div>
          ${this.config.show_status ? `<div class="status">${this._escape(status)}</div>` : ""}
        </div>
        <div class="body">${videoBlock}</div>
        <div class="actions">
          <button ${this.config.button_entity ? "" : "disabled"} id="open-btn">${this._escape(this.config.open_text)}</button>
          <button class="refresh" id="refresh-btn" title="Обновить / переподключить">↻</button>
        </div>
        ${this.config.show_hint ? `<div class="hint">${this._escape(hint)}</div>` : ""}
      </ha-card>
    `;

    this.shadowRoot.getElementById("open-btn")?.addEventListener("click", () => this._openDoor());
    this.shadowRoot.getElementById("refresh-btn")?.addEventListener("click", () => this._refresh());

    if (mode === "whep" && whepProxyPath && this.config.auto_start) {
      clearTimeout(this._whepAutostartTimer);
      const delay = Math.max(0, Number(this.config.auto_start_delay || 0));
      this._whepAutostartTimer = setTimeout(() => this._startWhep(whepProxyPath), delay);
    }
  }

  async _restartWhep() {
    this._stopWhep();
    this.render(true);
    const cameraState = this._getCameraState();
    const whepProxyPath = this._getWhepProxyPath(cameraState);
    if (whepProxyPath) {
      await this._startWhep(whepProxyPath, true);
    }
  }

  _stopWhep() {
    clearTimeout(this._whepTimeoutTimer);
    clearTimeout(this._whepRetryTimer);
    clearTimeout(this._whepAutostartTimer);
    this._whepTimeoutTimer = null;
    this._whepRetryTimer = null;
    this._whepAutostartTimer = null;
    this._whepConnected = false;
    try {
      if (this._pc) {
        this._pc.getSenders?.().forEach((sender) => sender.track?.stop?.());
        this._pc.getReceivers?.().forEach((receiver) => receiver.track?.stop?.());
        this._pc.close();
      }
    } catch (err) {
      // ignore
    }
    this._pc = null;
    this._whepKey = null;
    this._whepStarting = false;
  }

  async _startWhep(proxyPath, force = false) {
    const video = this.shadowRoot?.getElementById("whep-video");
    const overlay = this.shadowRoot?.getElementById("whep-overlay");
    if (!video || !proxyPath) return;

    if (!force && this._pc && this._whepKey === proxyPath) return;
    if (this._whepStarting) return;

    this._whepStarting = true;
    this._whepConnected = false;
    this._setOverlay(overlay, "Подключение WHEP...");

    const hideOverlay = () => {
      this._whepConnected = true;
      clearTimeout(this._whepTimeoutTimer);
      this._whepRetryAttempt = 0;
      this._setOverlay(overlay, "", true);
    };
    video.onloadedmetadata = hideOverlay;
    video.onplaying = hideOverlay;
    video.oncanplay = hideOverlay;

    try {
      this._stopWhep();
      this._whepStarting = true;

      const pc = new RTCPeerConnection({
        iceServers: [],
        bundlePolicy: "max-bundle",
      });

      this._pc = pc;
      this._whepKey = proxyPath;

      pc.addTransceiver("video", { direction: "recvonly" });

      pc.ontrack = (event) => {
        const stream = event.streams?.[0] || new MediaStream([event.track]);
        video.srcObject = stream;
        video.play?.().then(hideOverlay).catch(() => {});
        hideOverlay();
      };

      pc.onconnectionstatechange = () => {
        if (["connected", "completed"].includes(pc.connectionState)) {
          this._whepConnected = true;
          clearTimeout(this._whepTimeoutTimer);
        }
        if (["failed", "disconnected", "closed"].includes(pc.connectionState)) {
          this._setOverlay(overlay, `WHEP: ${pc.connectionState}`);
          if (this.config.auto_retry && pc.connectionState !== "closed") {
            this._scheduleWhepRetry(proxyPath, overlay, `connection ${pc.connectionState}`);
          }
        }
      };

      this._whepTimeoutTimer = setTimeout(() => {
        if (!this._whepConnected && !video.srcObject && this.config.auto_retry) {
          this._scheduleWhepRetry(proxyPath, overlay, "timeout waiting video");
        }
      }, Math.max(3000, Number(this.config.connect_timeout || 10000)));

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await this._waitForIceGathering(pc, 3500);

      const localDescription = pc.localDescription;
      if (!localDescription?.sdp) {
        throw new Error("Не удалось создать SDP offer");
      }

      const response = await this._haFetch(proxyPath, {
        method: "POST",
        headers: {
          "Content-Type": "application/sdp",
          "Accept": "application/sdp, text/plain, */*",
        },
        body: localDescription.sdp,
      });

      const answerSdp = await response.text();
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${answerSdp.slice(0, 240)}`);
      }

      this._setOverlay(overlay, "Ожидание видео...");
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

      // In some browsers ontrack/onplaying fires before setRemoteDescription resolves.
      // If the stream is already attached or video has started, hide the waiting overlay.
      if (video.srcObject || video.readyState >= 2) {
        hideOverlay();
      }
    } catch (err) {
      const message = err?.message || err;
      this._stopWhep(false);
      if (this.config.auto_retry) {
        this._scheduleWhepRetry(proxyPath, overlay, message);
      } else {
        this._setOverlay(overlay, `WHEP ошибка: ${message}`);
      }
    } finally {
      this._whepStarting = false;
    }
  }

  _scheduleWhepRetry(proxyPath, overlay, reason = "") {
    clearTimeout(this._whepTimeoutTimer);
    clearTimeout(this._whepRetryTimer);

    const maxRetries = Math.max(0, Number(this.config.retry_count || 0));
    if (this._whepRetryAttempt >= maxRetries) {
      this._setOverlay(overlay, `WHEP не подключился${reason ? `: ${reason}` : ""}`);
      return;
    }

    this._whepRetryAttempt += 1;
    const delay = Math.max(500, Number(this.config.retry_delay || 2500));
    this._setOverlay(overlay, `Повтор подключения ${this._whepRetryAttempt}/${maxRetries}...`);

    try {
      if (this._pc) {
        this._pc.getSenders?.().forEach((sender) => sender.track?.stop?.());
        this._pc.getReceivers?.().forEach((receiver) => receiver.track?.stop?.());
        this._pc.close();
      }
    } catch (err) {
      // ignore
    }
    this._pc = null;
    this._whepKey = null;
    this._whepStarting = false;
    this._whepConnected = false;

    this._whepRetryTimer = setTimeout(() => {
      this._startWhep(proxyPath, true);
    }, delay);
  }

  _waitForIceGathering(pc, timeoutMs = 3500) {
    if (pc.iceGatheringState === "complete") return Promise.resolve();
    return new Promise((resolve) => {
      const timer = setTimeout(resolve, timeoutMs);
      const check = () => {
        if (pc.iceGatheringState === "complete") {
          clearTimeout(timer);
          pc.removeEventListener("icegatheringstatechange", check);
          resolve();
        }
      };
      pc.addEventListener("icegatheringstatechange", check);
    });
  }

  async _haFetch(path, options = {}) {
    if (this._hass?.fetchWithAuth) {
      return this._hass.fetchWithAuth(path, options);
    }

    const headers = new Headers(options.headers || {});
    const token = this._getHassAccessToken();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    return fetch(path, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  }

  _getHassAccessToken() {
    try {
      const raw = localStorage.getItem("hassTokens");
      if (!raw) return null;
      const tokens = JSON.parse(raw);
      return tokens?.access_token || null;
    } catch (err) {
      return null;
    }
  }

  _setOverlay(overlay, text, hide = false) {
    if (!overlay) return;
    overlay.textContent = text || "";
    overlay.classList.toggle("hidden", Boolean(hide));
  }

  _escape(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

customElements.define("etd-intercom-card", ETDIntercomCard);



class ETDIntercomOverviewCard extends HTMLElement {
  setConfig(config) {
    this.config = {
      title: config.title || "ETD Intercom",
      columns: Number(config.columns || 2),
      mobile_columns: Number(config.mobile_columns || 1),
      full_width: config.full_width === true,
      max_width: config.max_width || "1600px",
      height: Number(config.height || 220),
      video_mode: config.video_mode || "preview", // preview | iframe | whep
      video_fit: config.video_fit || "cover",
      iframe_zoom: Number(config.iframe_zoom || 1),
      compact: config.compact === true,
      open_text: config.open_text || "Открыть",
      sort: config.sort !== false,
      show_header: config.show_header !== false,
      show_count: config.show_count !== false,
      show_status: config.show_status !== false,
      auto_start: config.auto_start === true,
      auto_retry: config.auto_retry !== false,
      retry_count: Number(config.retry_count || 3),
      retry_delay: Number(config.retry_delay || 2500),
      connect_timeout: Number(config.connect_timeout || 10000),
      start_stagger: Number(config.start_stagger || 700),
      include: config.include || null,
      exclude: config.exclude || null,
      ...config,
    };

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    this._lastKey = null;
    this._children = [];
  }

  set hass(hass) {
    this._hass = hass;
    const key = this._buildKey();
    if (key !== this._lastKey || !this.shadowRoot?.hasChildNodes()) {
      this.render();
      this._lastKey = key;
    } else {
      this._children.forEach((child) => {
        child.hass = hass;
      });
    }
  }

  getCardSize() {
    return 12;
  }

  getGridOptions() {
    return {
      rows: 8,
      columns: 12,
      min_rows: 4,
      max_rows: 12,
      min_columns: 6,
      max_columns: 12,
    };
  }

  _buildKey() {
    const pairs = this._discoverPairs();
    return JSON.stringify({
      count: pairs.length,
      ids: pairs.map((p) => `${p.intercom_id}:${p.camera_entity}:${p.button_entity}:${p.name}`),
      title: this.config.title,
      columns: this.config.columns,
      mobile_columns: this.config.mobile_columns,
      full_width: this.config.full_width,
      max_width: this.config.max_width,
      height: this.config.height,
      mode: this.config.video_mode,
      video_fit: this.config.video_fit,
      iframe_zoom: this.config.iframe_zoom,
      compact: this.config.compact,
      include: this.config.include,
      exclude: this.config.exclude,
      auto_start: this.config.auto_start,
      auto_retry: this.config.auto_retry,
      retry_count: this.config.retry_count,
      retry_delay: this.config.retry_delay,
      connect_timeout: this.config.connect_timeout,
      start_stagger: this.config.start_stagger,
      show_status: this.config.show_status,
    });
  }

  _discoverPairs() {
    if (!this._hass?.states) return [];

    const byId = new Map();

    for (const [entityId, state] of Object.entries(this._hass.states)) {
      const attrs = state.attributes || {};
      const intercomId = attrs.intercom_id;
      if (!intercomId) continue;

      const isETD = entityId.startsWith("button.etd_") || entityId.startsWith("camera.etd_") || attrs.camera_whep_proxy_path || attrs.camera_embed_link;
      if (!isETD) continue;

      const key = String(intercomId);
      const item = byId.get(key) || {
        intercom_id: key,
        name: attrs.friendly_name || attrs.etd_name || key,        source: attrs.source || "",
        camera_entity: null,
        button_entity: null,
      };

      if (attrs.etd_name) item.name = attrs.etd_name;
      if (attrs.source) item.source = attrs.source;

      if (entityId.startsWith("camera.")) item.camera_entity = entityId;
      if (entityId.startsWith("button.")) item.button_entity = entityId;

      byId.set(key, item);
    }

    let pairs = Array.from(byId.values()).filter((item) => item.camera_entity || item.button_entity);
    pairs = this._applyFilters(pairs);

    if (this.config.sort) {
      pairs.sort((a, b) => this._sortKey(a).localeCompare(this._sortKey(b), "ru", { numeric: true }));
    }

    return pairs;
  }

  _applyFilters(items) {
    const include = this._normalizeList(this.config.include);
    const exclude = this._normalizeList(this.config.exclude);

    return items.filter((item) => {
      const haystack = `${item.intercom_id} ${item.name} ${item.source}`.toLowerCase();
      if (include.length && !include.some((part) => haystack.includes(part))) return false;
      if (exclude.length && exclude.some((part) => haystack.includes(part))) return false;
      return true;
    });
  }

  _normalizeList(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value.map((v) => String(v).toLowerCase().trim()).filter(Boolean);
    return String(value)
      .split(",")
      .map((v) => v.toLowerCase().trim())
      .filter(Boolean);
  }

  _sortKey(item) {
    const name = String(item.name || "").toLowerCase();
    const id = String(item.intercom_id || "");
    const numMatch = name.match(/(\d+)/);
    const num = numMatch ? String(numMatch[1]).padStart(4, "0") : id.padStart(6, "0");

    if (name.includes("калит")) return `01-${num}-${name}`;
    if (name.includes("ворот")) return `02-${num}-${name}`;
    if (name.includes("подъезд") || name.includes("парад")) return `03-${num}-${name}`;
    return `09-${name}-${id}`;
  }

  render() {
    if (!this.shadowRoot || !this._hass) return;

    const pairs = this._discoverPairs();
    this._children = [];

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          width: ${this.config.full_width ? `min(${this.config.max_width}, calc(100vw - 48px))` : "100%"};
          max-width: ${this.config.full_width ? this.config.max_width : "100%"};
          ${this.config.full_width ? "margin-left: 50%; transform: translateX(-50%);" : ""}
          box-sizing: border-box;
        }
        ha-card {
          width: 100%;
          border-radius: 24px;
          background: transparent;
          box-shadow: none;
          border: 0;
          box-sizing: border-box;
        }
        .top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin: 0 0 12px;
          padding: 0 2px;
        }
        .title {
          font-size: 18px;
          font-weight: 700;
          color: var(--primary-text-color);
        }
        .count {
          font-size: 12px;
          color: var(--secondary-text-color);
          opacity: .8;
        }
        .grid {
          display: grid;
          grid-template-columns: repeat(${Math.max(1, this.config.columns)}, minmax(0, 1fr));
          gap: 14px;
        }
        .empty {
          padding: 18px;
          border-radius: 18px;
          background: rgba(35, 40, 55, 0.35);
          color: var(--secondary-text-color);
          border: 1px solid rgba(255,255,255,0.08);
        }
        @media (max-width: 760px) {
          .grid { grid-template-columns: repeat(${Math.max(1, this.config.mobile_columns)}, minmax(0, 1fr)); }
        }
      </style>
      <ha-card>
        ${this.config.show_header ? `
          <div class="top">
            <div class="title">${this._escape(this.config.title)}</div>
            ${this.config.show_count ? `<div class="count">${pairs.length} устройств</div>` : ""}
          </div>` : ""}
        <div class="grid" id="grid"></div>
      </ha-card>
    `;

    const grid = this.shadowRoot.getElementById("grid");
    if (!grid) return;

    if (!pairs.length) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "ETD-устройства не найдены. Проверь, что интеграция добавлена и есть camera/button сущности.";
      grid.appendChild(empty);
      return;
    }

    pairs.forEach((pair, index) => {
      const card = document.createElement("etd-intercom-card");
      card.setConfig({
        title: pair.name,
        camera_entity: pair.camera_entity,
        button_entity: pair.button_entity,
        height: this.config.height,
        video_mode: this.config.video_mode,
        video_fit: this.config.video_fit,
        iframe_zoom: this.config.iframe_zoom,
        compact: this.config.compact,
        open_text: this.config.open_text,
        show_status: this.config.show_status,
        show_hint: this.config.show_hint === true,
        auto_start: this.config.auto_start,
        auto_start_delay: this.config.auto_start ? index * Math.max(0, Number(this.config.start_stagger || 0)) : 0,
        auto_retry: this.config.auto_retry,
        retry_count: this.config.retry_count,
        retry_delay: this.config.retry_delay,
        connect_timeout: this.config.connect_timeout,
        show_preview_if_no_video: this.config.show_preview_if_no_video !== false,
      });
      card.hass = this._hass;
      this._children.push(card);
      grid.appendChild(card);
    });
  }

  _escape(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

customElements.define("etd-intercom-overview-card", ETDIntercomOverviewCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "etd-intercom-card",
  name: "ETD Intercom Card",
  preview: true,
  description: "ETD intercom live iframe/WHEP view with open button",
});


window.customCards.push({
  type: "etd-intercom-overview-card",
  name: "ETD Intercom Overview",
  preview: true,
  description: "Auto-generated grid of all ETD intercom cards",
});
