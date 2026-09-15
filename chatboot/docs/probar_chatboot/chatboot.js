const state = {
  socket: null,
  sessionId: null,
  channel: "exploracion",
  currentRequest: null,
  streamCount: 0,
  streamBubble: null,
  siteContext: null,
  pendingAutoMessage: null,
  lastIdsAsociados: [],
};

const SCENARIOS = {
  "exploracion-pregunta-directa": {
    channel: "exploracion",
    message: "Cuéntame sobre la Casa Museo de Riobamba",
    siteId: null,
  },
  "exploracion-museos": {
    channel: "exploracion",
    message: "Hola, quiero museos abiertos cerca de mí",
    siteId: null,
  },
  "sitio-horario": {
    channel: "pregunta_directa",
    message: "¿Cuál es el horario de atención?",
    siteId: 68,
    siteName: "Mercado de la Merced",
  },
  "sitio-precio": {
    channel: "pregunta_directa",
    message: "¿Cuánto cuesta la entrada?",
    siteId: 68,
    siteName: "Mercado de la Merced",
  },
};

const elements = {
  baseUrl: document.getElementById("baseUrl"),
  channel: document.getElementById("channel"),
  message: document.getElementById("message"),
  siteId: document.getElementById("siteId"),
  siteIdWrap: document.getElementById("siteIdWrap"),
  siteName: document.getElementById("siteName"),
  siteNameWrap: document.getElementById("siteNameWrap"),
  userId: document.getElementById("userId"),
  location: document.getElementById("location"),
  sessionInput: document.getElementById("sessionInput"),
  connectBtn: document.getElementById("connectBtn"),
  disconnectBtn: document.getElementById("disconnectBtn"),
  sendBtn: document.getElementById("sendBtn"),
  sendForm: document.getElementById("sendForm"),
  newSessionBtn: document.getElementById("newSessionBtn"),
  backExploracionBtn: document.getElementById("backExploracionBtn"),
  status: document.getElementById("status"),
  responseTime: document.getElementById("responseTime"),
  streamCount: document.getElementById("streamCount"),
  socketUrl: document.getElementById("socketUrl"),
  sessionBadge: document.getElementById("sessionBadge"),
  phoneTitle: document.getElementById("phoneTitle"),
  phoneSubtitle: document.getElementById("phoneSubtitle"),
  siteContextBar: document.getElementById("siteContextBar"),
  siteContextName: document.getElementById("siteContextName"),
  siteContextId: document.getElementById("siteContextId"),
  chatMessages: document.getElementById("chatMessages"),
  classificationJson: document.getElementById("classificationJson"),
  executionJson: document.getElementById("executionJson"),
  outboundJson: document.getElementById("outboundJson"),
  planStatus: document.getElementById("planStatus"),
  idsSummary: document.getElementById("idsSummary"),
};

function normalizeMarkdownText(text) {
  return String(text || "")
    .replace(/\\\*\\\*/g, "**")
    .replace(/\\\* /g, "* ")
    .replace(/\\\*/g, "*");
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function markdownToHtml(text) {
  const normalized = normalizeMarkdownText(text);
  const escaped = escapeHtml(normalized);
  return escaped
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/\n/g, "<br>");
}

function setRichTextContent(element, text) {
  element.innerHTML = markdownToHtml(text);
}

function shouldShowBubbleLabel(label) {
  if (!label) {
    return false;
  }
  const key = String(label).toLowerCase();
  return key === "error" || key === "validación" || key === "sistema";
}

function uuid() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `client_${Math.random().toString(16).slice(2)}_${Date.now()}`;
}

function buildSocketUrl() {
  const base = elements.baseUrl.value.trim().replace(/\/+$/, "");
  const path = elements.channel.value === "exploracion"
    ? "/ws/exploracion"
    : "/ws/pregunta_directa";
  return `${base}${path}`;
}

function buildHttpBaseUrl() {
  return elements.baseUrl.value
    .trim()
    .replace(/^wss:/, "https:")
    .replace(/^ws:/, "http:")
    .replace(/\/+$/, "");
}

function resolveAssetUrl(url) {
  const value = String(url || "").trim();
  if (!value) {
    return "";
  }
  if (/^https?:\/\//i.test(value)) {
    return value;
  }
  return `${buildHttpBaseUrl()}${value.startsWith("/") ? "" : "/"}${value}`;
}

function setStatus(text) {
  elements.status.textContent = text;
}

function setSocketUrl() {
  elements.socketUrl.textContent = buildSocketUrl();
}

function setResponseTime(value) {
  elements.responseTime.textContent = value;
}

function setStreamCount(value) {
  state.streamCount = value;
  elements.streamCount.textContent = String(value);
}

function setJson(node, value) {
  node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function updateSession(sessionId) {
  if (sessionId) {
    state.sessionId = sessionId;
    elements.sessionInput.value = sessionId;
    elements.sessionBadge.textContent = sessionId;
  } else {
    state.sessionId = null;
    elements.sessionInput.value = "";
    elements.sessionBadge.textContent = "sin sesión";
  }
}

function updateChannelUi() {
  const isSiteChat = elements.channel.value === "pregunta_directa";
  state.channel = elements.channel.value;

  elements.siteIdWrap.hidden = !isSiteChat;
  elements.siteNameWrap.hidden = !isSiteChat;
  elements.backExploracionBtn.hidden = !isSiteChat;
  elements.phoneSubtitle.textContent = isSiteChat
    ? "Chat del sitio"
    : "Exploración turística";
  elements.phoneTitle.textContent = isSiteChat && state.siteContext?.nombre
    ? state.siteContext.nombre
    : "RiobambaGo";
  elements.message.placeholder = isSiteChat
    ? "Pregunta sobre este sitio turístico..."
    : "Escribe una consulta turística...";

  if (isSiteChat && state.siteContext?.id_sitio) {
    elements.siteId.value = String(state.siteContext.id_sitio);
    elements.siteName.value = state.siteContext.nombre || elements.siteName.value;
    updateSiteContextBar();
  } else if (!isSiteChat) {
    hideSiteContextBar();
  }
}

function updateSiteContextBar() {
  if (!state.siteContext?.id_sitio) {
    hideSiteContextBar();
    return;
  }
  elements.siteContextBar.hidden = false;
  elements.siteContextName.textContent = state.siteContext.nombre || "Sitio turístico";
  elements.siteContextId.textContent = `id_sitio ${state.siteContext.id_sitio}`;
}

function hideSiteContextBar() {
  elements.siteContextBar.hidden = true;
}

function clearChat() {
  elements.chatMessages.innerHTML = "";
}

function ensureChatNotEmpty() {
  const empty = elements.chatMessages.querySelector(".empty-state");
  if (empty) {
    empty.remove();
  }
}

function scrollChat() {
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function addBubble({ text, role = "bot", label = "", system = false }) {
  ensureChatNotEmpty();
  const bubble = document.createElement("article");
  bubble.className = `bubble ${role}${system ? " system" : ""}`;
  if (shouldShowBubbleLabel(label)) {
    const small = document.createElement("small");
    small.textContent = label;
    bubble.appendChild(small);
  }
  const body = document.createElement("div");
  body.className = "bubble-body";
  setRichTextContent(body, text || "");
  bubble.appendChild(body);
  elements.chatMessages.appendChild(bubble);
  scrollChat();
  return bubble;
}

function upsertStreamBubble({ text, label = "" }) {
  ensureChatNotEmpty();
  if (!state.streamBubble || !elements.chatMessages.contains(state.streamBubble)) {
    state.streamBubble = document.createElement("article");
    state.streamBubble.className = "bubble stream";

    const small = document.createElement("small");
    small.dataset.role = "label";

    const body = document.createElement("div");
    body.dataset.role = "text";

    state.streamBubble.append(small, body);
    elements.chatMessages.appendChild(state.streamBubble);
  }

  const labelNode = state.streamBubble.querySelector('[data-role="label"]');
  const bodyNode = state.streamBubble.querySelector('[data-role="text"]');
  labelNode.textContent = label || "progreso";
  setRichTextContent(bodyNode, text || "");
  scrollChat();
}

function clearStreamBubble() {
  if (state.streamBubble && elements.chatMessages.contains(state.streamBubble)) {
    state.streamBubble.remove();
  }
  state.streamBubble = null;
}

function createCardNode(message) {
  const card = document.createElement("article");
  card.className = "site-card";

  const imageUrl = resolveAssetUrl(
    message.imagen_url || message.img_Url || message.imagen_principal
  );
  const imageWrap = document.createElement("div");
  imageWrap.className = "site-card-image";
  if (imageUrl) {
    const image = document.createElement("img");
    image.src = imageUrl;
    image.alt = message.nombre_sitio || message.nombre || "Imagen del sitio";
    image.loading = "lazy";
    imageWrap.appendChild(image);
  } else {
    imageWrap.textContent = "Sin imagen";
  }

  const content = document.createElement("div");
  content.className = "site-card-content";

  const category = document.createElement("span");
  category.className = "site-card-category";
  category.textContent = message.categoria || "Sin categoría";

  const title = document.createElement("strong");
  title.textContent = message.nombre_sitio || message.nombre || "Sitio turístico";

  const address = document.createElement("span");
  address.className = "site-card-address";
  const distancia = message.distancia_aproximada;
  if (distancia) {
    address.textContent = `A ~${distancia}`;
  } else {
    address.textContent = message.direccion || "Dirección no disponible";
  }

  if (distancia && message.direccion) {
    const extra = document.createElement("span");
    extra.className = "site-card-extra";
    extra.textContent = message.direccion;
    content.append(category, title, address, extra);
  } else {
    content.append(category, title, address);
  }
  card.append(imageWrap, content);
  return card;
}

function addCard(message) {
  ensureChatNotEmpty();
  elements.chatMessages.appendChild(createCardNode(message));
  scrollChat();
}

function addResultsGroup(cards) {
  if (!Array.isArray(cards) || cards.length === 0) {
    return;
  }
  ensureChatNotEmpty();

  const panel = document.createElement("section");
  panel.className = "results-panel";

  const title = document.createElement("h3");
  title.textContent = "Resultados";

  const row = document.createElement("div");
  row.className = "results-row";
  cards.forEach((messageApp) => {
    row.appendChild(createCardNode(messageApp.mensaje || {}));
  });

  panel.append(title, row);
  elements.chatMessages.appendChild(panel);
  scrollChat();
}

function rememberIdsAsociados(ids) {
  if (!Array.isArray(ids) || ids.length === 0) {
    return;
  }
  state.lastIdsAsociados = ids;
}

function clearIdsAsociados() {
  state.lastIdsAsociados = [];
}

function addCatalogSummary({ total, visible }) {
  if (!total || total <= 0) {
    return;
  }
  ensureChatNotEmpty();
  const panel = document.createElement("section");
  panel.className = "catalog-summary";

  const title = document.createElement("strong");
  title.textContent = total === 1 ? "1 lugar encontrado" : `${total} lugares encontrados`;

  const detail = document.createElement("span");
  if (visible > 0) {
    detail.textContent = `Mostrando ${visible} tarjeta${visible === 1 ? "" : "s"} como en la app móvil.`;
  } else {
    detail.textContent = "Desliza para ver opciones o usa catálogo/mapa en la app.";
  }

  panel.append(title, detail);
  elements.chatMessages.appendChild(panel);
  scrollChat();
}

function buildFallbackCards(exploracion, idsAsociados) {
  const estados = exploracion.estados_herramientas || [];
  const byId = new Map();

  estados.forEach((estado) => {
    const payload = estado?.payload || {};
    const candidatos = payload.candidatos;
    if (!Array.isArray(candidatos)) {
      return;
    }
    candidatos.forEach((candidato) => {
      const id = candidato?.id_sitio || candidato?.id_ruta;
      if (id) {
        byId.set(Number(id), candidato);
      }
    });
  });

  const ids = (idsAsociados || []).slice(0, 5);
  return ids.map((id) => {
    const candidato = byId.get(id) || {};
    return {
      tipo: "card",
      mensaje: {
        id_sitio: id,
        nombre_sitio: candidato.nombre || candidato.titulo || `Sitio ${id}`,
        categoria: candidato.categoria || "Turismo",
        direccion: candidato.direccion || "",
        distancia_aproximada: candidato.distancia_aproximada || "",
        imagen_url: candidato.imagen_url || candidato.img_Url || "",
      },
    };
  });
}

function addIds(ids) {
  rememberIdsAsociados(ids);
}

function addOptions(options) {
  if (!Array.isArray(options) || options.length === 0) {
    return;
  }
  ensureChatNotEmpty();
  const list = document.createElement("div");
  list.className = "option-list";
  options.forEach((option) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "option-chip";
    item.textContent = String(option);
    item.addEventListener("click", () => {
      elements.message.value = String(option);
      sendMessage();
    });
    list.appendChild(item);
  });
  elements.chatMessages.appendChild(list);
  scrollChat();
}

function openSiteChatbotFromAction(message) {
  const idSitio = Number(message.id_sitio);
  if (!Number.isInteger(idSitio) || idSitio <= 0) {
    addBubble({
      text: "La acción no incluyó un id_sitio válido.",
      role: "bot",
      label: "error",
    });
    return;
  }

  state.siteContext = {
    id_sitio: idSitio,
    nombre: message.nombre_sitio || `Sitio ${idSitio}`,
  };

  addBubble({
    text: `Abriendo chat de ${state.siteContext.nombre}...`,
    role: "bot",
    system: true,
  });

  elements.channel.value = "pregunta_directa";
  clearIdsAsociados();
  updateChannelUi();
  elements.siteId.value = String(idSitio);
  elements.siteName.value = state.siteContext.nombre;
  state.pendingAutoMessage = null;

  disconnectSocket();
  setSocketUrl();
  connectSocket({
    onReady: () => {
      addBubble({
        text: `Estás en el chat específico de ${state.siteContext.nombre}. Pregunta horarios, precios o detalles del lugar.`,
        role: "bot",
        system: true,
      });
    },
  });
}

function addAction(message) {
  if (!message || typeof message !== "object") {
    return;
  }
  ensureChatNotEmpty();
  const action = document.createElement("button");
  action.type = "button";
  action.className = "action-button";
  action.textContent = message.label || "Abrir chatbot del sitio";
  action.addEventListener("click", () => {
    if (message.accion === "abrir_google_maps" && message.url) {
      window.open(message.url, "_blank", "noopener,noreferrer");
      return;
    }
    openSiteChatbotFromAction(message);
  });
  elements.chatMessages.appendChild(action);
  scrollChat();
}

function addMultimedia(message) {
  const images = Array.isArray(message.imagenes) ? message.imagenes : [];
  if (images.length === 0) {
    return;
  }
  ensureChatNotEmpty();
  const gallery = document.createElement("section");
  gallery.className = "media-gallery";
  images.forEach((item, index) => {
    const url = resolveAssetUrl(item.url || item.imagen_url || item.src);
    if (!url) {
      return;
    }
    const image = document.createElement("img");
    image.src = url;
    image.alt = item.es_principal
      ? "Imagen principal del sitio"
      : `Imagen del sitio ${index + 1}`;
    image.loading = "lazy";
    gallery.appendChild(image);
  });
  if (!gallery.childElementCount) {
    return;
  }
  elements.chatMessages.appendChild(gallery);
  scrollChat();
}

function renderMessageApp(messageApp, { skipStream = false } = {}) {
  if (!messageApp || typeof messageApp !== "object") {
    return;
  }
  const tipo = messageApp.tipo;
  const mensaje = messageApp.mensaje || {};

  if (tipo === "stream") {
    if (!skipStream) {
      upsertStreamBubble({
        text: mensaje.texto || "",
        label: mensaje.fase || mensaje.origen || "progreso",
      });
    }
    return;
  }

  if (tipo === "globo") {
    addBubble({
      text: mensaje.texto || "",
      role: "bot",
      label: mensaje.origen || "chatboot",
    });
    return;
  }

  if (tipo === "card") {
    addCard(mensaje);
    return;
  }

  if (tipo === "multimedia") {
    addMultimedia(mensaje);
    return;
  }

  if (tipo === "ids_asociados") {
    rememberIdsAsociados(mensaje.ids_asociados || []);
    return;
  }

  if (tipo === "opciones") {
    addOptions(mensaje.opciones || []);
    return;
  }

  if (tipo === "accion") {
    addAction(mensaje);
  }
}

function renderMensajesApp(
  mensajes,
  { skipStream = false, exploracion = null, allowCatalogFallback = false } = {},
) {
  if (!Array.isArray(mensajes) || mensajes.length === 0) {
    return { cardsRendered: 0, idsCount: 0 };
  }

  let cardsPendientes = [];
  let cardsRendered = 0;
  let idsCount = 0;

  mensajes.forEach((messageApp) => {
    if (messageApp?.tipo === "card") {
      cardsPendientes.push(messageApp);
      return;
    }
    if (cardsPendientes.length) {
      addResultsGroup(cardsPendientes);
      cardsRendered += cardsPendientes.length;
      cardsPendientes = [];
    }
    if (messageApp?.tipo === "ids_asociados") {
      const ids = messageApp.mensaje?.ids_asociados || [];
      idsCount = ids.length;
      if (allowCatalogFallback) {
        rememberIdsAsociados(ids);
      }
      return;
    }
    renderMessageApp(messageApp, { skipStream });
  });

  if (cardsPendientes.length) {
    addResultsGroup(cardsPendientes);
    cardsRendered += cardsPendientes.length;
  }

  const idsAsociados = allowCatalogFallback
    ? exploracion?.ids_asociados || state.lastIdsAsociados || []
    : [];
  if (allowCatalogFallback && cardsRendered === 0 && idsAsociados.length > 0) {
    const fallbackCards = buildFallbackCards(exploracion || {}, idsAsociados);
    if (fallbackCards.length > 0) {
      addResultsGroup(fallbackCards);
      cardsRendered = fallbackCards.length;
    }
  }

  if (allowCatalogFallback && idsAsociados.length > 0) {
    addCatalogSummary({ total: idsAsociados.length, visible: cardsRendered });
  }

  return { cardsRendered, idsCount: idsAsociados.length || idsCount };
}

function renderFinalPayload(payload) {
  const exploracion = payload.exploracion || {};
  const preguntaDirecta = payload.pregunta_directa || {};
  const mensajesPreguntaDirecta = Array.isArray(preguntaDirecta.mensajes_app)
    ? preguntaDirecta.mensajes_app
    : [];
  if (payload.pregunta_chatboot === "pregunta_directa" && mensajesPreguntaDirecta.length > 0) {
    renderMensajesApp(mensajesPreguntaDirecta, {
      skipStream: true,
      allowCatalogFallback: false,
    });
    return;
  }

  const mensajesExploracion = Array.isArray(exploracion.mensajes_app)
    ? exploracion.mensajes_app
    : [];

  if (mensajesExploracion.length > 0) {
    renderMensajesApp(mensajesExploracion, {
      skipStream: true,
      exploracion,
      allowCatalogFallback: true,
    });
    return;
  }

  if (Array.isArray(exploracion.ids_asociados) && exploracion.ids_asociados.length > 0) {
    rememberIdsAsociados(exploracion.ids_asociados);
    const fallbackCards = buildFallbackCards(exploracion, exploracion.ids_asociados);
    if (fallbackCards.length > 0) {
      addResultsGroup(fallbackCards);
    }
    addCatalogSummary({
      total: exploracion.ids_asociados.length,
      visible: fallbackCards.length,
    });
  }

  if (payload.mensaje_app) {
    renderMessageApp(payload.mensaje_app, { skipStream: true });
    return;
  }

  if (payload.mensaje_sistema) {
    addBubble({
      text: payload.mensaje_sistema,
      role: "bot",
      label: payload.pregunta_chatboot || "chatboot",
    });
  }
}

function extractSession(payload) {
  return payload?.payload?.sesion_id
    || payload?.payload?.sesion_Id
    || payload?.sesion_id
    || payload?.sesion_Id
    || null;
}

function updateTechnicalPanels(payload) {
  const exploracion = payload.exploracion || {};
  const preguntaDirecta = payload.pregunta_directa || {};
  const planPayload = payload.pregunta_chatboot === "pregunta_directa"
    ? preguntaDirecta
    : exploracion;
  const classification = {
    pregunta_chatboot: payload.pregunta_chatboot || state.channel,
    id_sitio: payload.id_sitio ?? state.siteContext?.id_sitio ?? null,
    nombre_sitio: payload.nombre_sitio ?? state.siteContext?.nombre ?? null,
    plan_valido: planPayload.plan_valido ?? null,
    plan: planPayload.plan || null,
    errores_formato: planPayload.errores_formato || [],
    texto_limpio: payload.mensaje?.texto_limpio,
    riesgo_prompt_inyection: payload.mensaje?.riesgo_prompt_inyection,
    palabras_inyectadas: payload.mensaje?.palabras_inyectadas || [],
  };
  const execution = {
    estados_herramientas: planPayload.estados_herramientas || [],
    ids_asociados: planPayload.ids_asociados || state.lastIdsAsociados || [],
    mensajes_app: planPayload.mensajes_app || [],
    pregunta_directa: payload.pregunta_directa || null,
    mensaje_app_principal: payload.mensaje_app || null,
    canal_activo: state.channel,
    site_context: state.siteContext,
  };

  setJson(elements.classificationJson, classification);
  setJson(elements.executionJson, execution);

  if (payload.pregunta_chatboot === "pregunta_directa") {
    elements.planStatus.textContent = classification.plan_valido === true
      ? `plan sitio válido · id ${payload.id_sitio ?? "-"}`
      : classification.plan_valido === false
        ? `plan sitio inválido · id ${payload.id_sitio ?? "-"}`
        : `canal sitio · id ${payload.id_sitio ?? "-"}`;
  } else if (classification.plan_valido === true) {
    elements.planStatus.textContent = "plan válido";
  } else if (classification.plan_valido === false) {
    elements.planStatus.textContent = "plan inválido";
  } else {
    elements.planStatus.textContent = exploracion.plan ? "sin validación" : "sin plan";
  }

  const ids = execution.ids_asociados;
  elements.idsSummary.textContent = Array.isArray(ids) && ids.length
    ? `${ids.length} ID${ids.length === 1 ? "" : "s"} (panel técnico)`
    : payload.id_sitio
      ? `sitio ${payload.id_sitio}`
      : "sin IDs";
}

function updateButtons() {
  const open = state.socket && state.socket.readyState === WebSocket.OPEN;
  elements.sendBtn.disabled = !open;
  elements.disconnectBtn.disabled = !state.socket;
  elements.connectBtn.disabled = Boolean(state.socket);
}

function disconnectSocket() {
  clearStreamBubble();
  if (state.socket) {
    state.socket.close();
    state.socket = null;
  }
  setStatus("desconectado");
  updateButtons();
}

function connectSocket({ onReady } = {}) {
  disconnectSocket();
  state.channel = elements.channel.value;
  setSocketUrl();
  setStatus("conectando");

  const socket = new WebSocket(buildSocketUrl());
  state.socket = socket;

  socket.addEventListener("open", () => {
    setStatus("inicializando chatboot...");
    updateChannelUi();
    updateButtons();
    if (typeof onReady === "function") {
      onReady();
    }
    if (state.pendingAutoMessage) {
      elements.message.value = state.pendingAutoMessage;
      state.pendingAutoMessage = null;
      sendMessage();
    }
  });

  socket.addEventListener("message", (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch {
      setJson(elements.executionJson, event.data);
      return;
    }

    if (payload.tipo === "conexion") {
      setStatus(payload.estado === "inicializando" ? "inicializando chatboot..." : "conectado");
      if (payload.pregunta_chatboot) {
        elements.planStatus.textContent = payload.estado === "inicializando"
          ? `inicializando ${payload.pregunta_chatboot}`
          : payload.pregunta_chatboot;
      }
      return;
    }

    if (payload.tipo === "stream") {
      setStreamCount(state.streamCount + 1);
      const streamMessage = payload.payload?.tipo
        ? payload.payload
        : payload.payload;
      renderMessageApp(streamMessage);
      return;
    }

    if (payload.tipo === "clasificacion_final" && payload.payload) {
      clearStreamBubble();
      const elapsed = state.currentRequest
        ? performance.now() - state.currentRequest.startedAt
        : 0;
      setResponseTime(elapsed ? `${Math.round(elapsed)} ms` : "-");
      setStatus("respuesta recibida");

      const inner = payload.payload;
      const sessionId = extractSession(payload);
      if (sessionId) {
        updateSession(sessionId);
      }
      if (inner.id_sitio) {
        state.siteContext = {
          id_sitio: inner.id_sitio,
          nombre: inner.nombre_sitio || state.siteContext?.nombre || `Sitio ${inner.id_sitio}`,
        };
        elements.siteName.value = state.siteContext.nombre;
        updateSiteContextBar();
      }

      updateTechnicalPanels(inner);
      renderFinalPayload(inner);
      return;
    }

    if (payload.tipo === "error_validacion") {
      clearStreamBubble();
      setStatus("error");
      addBubble({
        text: payload.mensaje || "Error de validación",
        role: "bot",
        label: "error",
      });
      setJson(elements.executionJson, payload);
    }
  });

  socket.addEventListener("close", () => {
    state.socket = null;
    setStatus("desconectado");
    updateButtons();
  });

  socket.addEventListener("error", () => {
    setStatus("error");
    updateButtons();
  });

  updateButtons();
}

function parseLocation() {
  try {
    return JSON.parse(elements.location.value || "{}");
  } catch {
    throw new Error("ubicacion_usuario debe ser JSON válido");
  }
}

function buildOutboundPayload() {
  const ubicacion = parseLocation();
  const text = elements.message.value.trim();
  const clientMessageId = uuid();
  const explicitSession = elements.sessionInput.value.trim();
  const userId = Number(elements.userId.value);
  if (explicitSession) {
    state.sessionId = explicitSession;
  }

  if (!Number.isInteger(userId) || userId <= 0) {
    throw new Error("id_usuario debe ser un entero positivo para guardar historial.");
  }

  const payload = {
    mensaje_usuario: text,
    id_usuario: userId,
    client_message_id: clientMessageId,
    sesion_Id: state.sessionId || null,
    ubicacion_usuario: ubicacion,
  };

  if (state.channel === "pregunta_directa") {
    const siteId = Number(elements.siteId.value);
    const siteName = elements.siteName.value.trim();
    if (!Number.isInteger(siteId) || siteId <= 0) {
      throw new Error("id_sitio debe ser un entero positivo.");
    }
    if (!siteName) {
      throw new Error("nombre_sitio es obligatorio para pregunta directa.");
    }
    payload.id_sitio = siteId;
    payload.nombre_sitio = siteName;
    state.siteContext = { id_sitio: siteId, nombre: siteName };
    updateSiteContextBar();
  }

  return payload;
}

function sendMessage() {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    return;
  }

  let payload;
  try {
    payload = buildOutboundPayload();
  } catch (error) {
    addBubble({ text: error.message, role: "bot", label: "validación" });
    return;
  }

  if (!payload.mensaje_usuario) {
    return;
  }

  if (!state.sessionId && !elements.sessionInput.value.trim()) {
    updateSession(null);
  }

  setJson(elements.outboundJson, payload);
  setStreamCount(0);
  clearStreamBubble();
  setResponseTime("esperando...");
  setStatus("procesando");
  state.currentRequest = {
    clientMessageId: payload.client_message_id,
    startedAt: performance.now(),
  };
  addBubble({ text: payload.mensaje_usuario, role: "user" });
  state.socket.send(JSON.stringify(payload));
}

function returnToExploracion() {
  state.siteContext = null;
  hideSiteContextBar();
  elements.channel.value = "exploracion";
  updateChannelUi();
  disconnectSocket();
  setSocketUrl();
  addBubble({
    text: "Volviste al chat de exploración turística.",
    role: "bot",
    system: true,
  });
}

function applyScenario(scenarioKey) {
  const scenario = SCENARIOS[scenarioKey];
  if (!scenario) {
    return;
  }

  elements.message.value = scenario.message;
  elements.channel.value = scenario.channel;
  clearIdsAsociados();

  if (scenario.channel === "pregunta_directa") {
    const siteId = scenario.siteId || Number(elements.siteId.value) || 68;
    const siteName = scenario.siteName || elements.siteName.value.trim() || "Mercado de la Merced";
    state.siteContext = {
      id_sitio: siteId,
      nombre: siteName,
    };
    elements.siteId.value = String(siteId);
    elements.siteName.value = siteName;
  } else {
    state.siteContext = null;
  }

  updateChannelUi();
  setSocketUrl();

  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    state.pendingAutoMessage = scenario.message;
    connectSocket();
    return;
  }

  sendMessage();
}

elements.connectBtn.addEventListener("click", () => connectSocket());
elements.disconnectBtn.addEventListener("click", disconnectSocket);
elements.backExploracionBtn.addEventListener("click", returnToExploracion);

elements.newSessionBtn.addEventListener("click", () => {
  updateSession(null);
  clearIdsAsociados();
  clearStreamBubble();
  clearChat();
  elements.chatMessages.innerHTML = '<div class="empty-state">Nueva sesión lista.</div>';
  setJson(elements.outboundJson, "Aún no hay envíos.");
});

elements.channel.addEventListener("change", () => {
  clearIdsAsociados();
  if (elements.channel.value === "exploracion") {
    state.siteContext = null;
    hideSiteContextBar();
  }
  disconnectSocket();
  updateChannelUi();
  setSocketUrl();
});

elements.baseUrl.addEventListener("input", setSocketUrl);

elements.sendForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage();
});

elements.message.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    sendMessage();
  }
});

document.querySelectorAll("[data-scenario]").forEach((button) => {
  button.addEventListener("click", () => {
    applyScenario(button.dataset.scenario);
  });
});

setSocketUrl();
setStatus("desconectado");
setResponseTime("-");
setStreamCount(0);
setJson(elements.classificationJson, "Aún no hay clasificación.");
setJson(elements.executionJson, "Aún no hay ejecución.");
setJson(elements.outboundJson, "Aún no hay envíos.");
updateSession(null);
updateChannelUi();
updateButtons();
