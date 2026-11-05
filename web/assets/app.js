/* ============================================================
   中华农耕文化地图 — 交互
   数据：data/sites.geojson（由 web/build_data.py 生成）
   ============================================================ */

(() => {
  "use strict";

  const CATEGORIES = [
    { key: "rice", label: "稻作文化", color: "#c59a3f" },
    { key: "water", label: "梯田水利", color: "#3f7fa3" },
    { key: "tea", label: "茶文化", color: "#5c7a4a" },
    { key: "mulberry", label: "蚕桑渔农", color: "#8a5a44" },
    { key: "dryland", label: "旱作游牧", color: "#a9743a" },
    { key: "custom", label: "农事民俗", color: "#a63d40" },
    { key: "specialty", label: "特色物产", color: "#7a5c9e" },
  ];
  const CATEGORY_BY_KEY = new Map(CATEGORIES.map((c) => [c.key, c]));
  const MAINLAND_BOUNDS = [
    [17.2, 73.0],
    [53.8, 135.4],
  ];
  const MOBILE_QUERY = "(max-width: 900px)";
  const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";

  const $ = (selector) => document.querySelector(selector);
  const escapeMap = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (ch) => escapeMap[ch]);
  const isMobile = () => window.matchMedia(MOBILE_QUERY).matches;
  const prefersReducedMotion = () =>
    window.matchMedia(REDUCED_QUERY).matches;
  const categoryOf = (key) =>
    CATEGORY_BY_KEY.get(key) || {
      key,
      label: "农耕文化",
      color: "#b4552d",
    };

  const state = {
    sites: [],
    filtered: [],
    filteredIds: new Set(),
    selectedId: null,
    category: "all",
    province: "all",
    query: "",
    stats: null,
    provinceCounts: new Map(),
    map: null,
    insetMap: null,
    cluster: null,
    markerById: new Map(),
    hasDetail: false,
    lastFocus: null,
  };

  const els = {
    app: $("#app"),
    sidebar: $("#sidebar"),
    sidebarBackdrop: $("#sidebar-backdrop"),
    menuButton: $("#menu-button"),
    search: $("#search"),
    resetFilters: $("#reset-filters"),
    categoryChips: $("#category-chips"),
    provinceSelect: $("#province-select"),
    resultCount: $("#result-count"),
    siteList: $("#site-list"),
    statSites: $("#stat-sites"),
    statProvinces: $("#stat-provinces"),
    statCategories: $("#stat-categories"),
    mapWrap: $("#map-wrap"),
    mapCaptionMeta: $("#map-caption-meta"),
    legend: $("#legend"),
    resetView: $("#reset-view"),
    aboutButton: $("#about-button"),
    aboutButtonMap: $("#about-button-map"),
    aboutModal: $("#about-modal"),
    detail: $("#detail"),
    detailScroll: $("#detail-scroll"),
    detailClose: $("#detail-close"),
    toast: $("#toast"),
  };

  let toastTimer = null;
  let searchTimer = null;
  let lastModalFocus = null;

  /* ---------- 数据载入 ---------- */

  async function loadJson(url) {
    const response = await fetch(url, { cache: "no-cache" });
    if (!response.ok) {
      throw new Error(`${url}: HTTP ${response.status}`);
    }
    return response.json();
  }

  async function init() {
    if (typeof L === "undefined") {
      throw new Error("Leaflet 未能载入，请确认 vendor/leaflet 文件完整。");
    }

    const [sitesGeo, stats, provinces] = await Promise.all([
      loadJson("data/sites.geojson"),
      loadJson("data/stats.json"),
      loadJson("data/provinces.geojson"),
    ]);

    state.sites = sitesGeo.features.map((feature) => ({
      ...feature.properties,
      lng: feature.geometry.coordinates[0],
      lat: feature.geometry.coordinates[1],
    }));
    state.stats = stats;
    state.provinceCounts = new Map(
      Object.entries(stats.provinceCounts || {}),
    );

    renderStats();
    renderChips();
    renderProvinceOptions();
    renderLegend();
    initMap(provinces);
    initMarkers();
    bindEvents();
    syncSidebarInert();
    restoreFromHash(true);

    els.mapCaptionMeta.textContent = `${state.sites.length} 处 · 点击地标查看详情`;
  }

  function renderStats() {
    const stats = state.stats;
    els.statSites.textContent = stats.total;
    els.statProvinces.textContent = stats.provinces;
    els.statCategories.textContent = Object.values(stats.categories).filter(
      (item) => item.count > 0,
    ).length;
  }

  function renderChips() {
    const counts = new Map(
      Object.entries(state.stats?.categories || {}).map(([key, value]) => [
        key,
        value.count,
      ]),
    );
    const fragment = document.createDocumentFragment();
    const all = document.createElement("button");
    all.type = "button";
    all.className = "chip";
    all.dataset.category = "all";
    all.setAttribute("aria-pressed", "true");
    all.innerHTML = `全部<span class="chip__count">${state.sites.length}</span>`;
    fragment.appendChild(all);

    for (const category of CATEGORIES) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chip";
      button.dataset.category = category.key;
      button.setAttribute("aria-pressed", "false");
      button.innerHTML = `<span class="chip__dot" style="--dot:${category.color}"></span>${category.label}<span class="chip__count">${counts.get(category.key) || 0}</span>`;
      fragment.appendChild(button);
    }

    els.categoryChips.replaceChildren(fragment);
    syncChips();
  }

  function renderProvinceOptions() {
    const names = [...state.provinceCounts.keys()].sort((a, b) =>
      a.localeCompare(b, "zh-Hans-CN"),
    );
    const fragment = document.createDocumentFragment();
    const all = document.createElement("option");
    all.value = "all";
    all.textContent = `全部省份（${state.sites.length}）`;
    fragment.appendChild(all);
    for (const name of names) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = `${name}（${state.provinceCounts.get(name)}）`;
      fragment.appendChild(option);
    }
    els.provinceSelect.replaceChildren(fragment);
    els.provinceSelect.value = state.province;
  }

  function renderLegend() {
    const fragment = document.createDocumentFragment();
    const title = document.createElement("div");
    title.className = "legend-title";
    title.textContent = "图例";
    fragment.appendChild(title);
    for (const category of CATEGORIES) {
      const item = document.createElement("div");
      item.className = "legend-item";
      item.innerHTML = `<span class="legend-dot" style="--dot:${category.color}"></span>${category.label}`;
      fragment.appendChild(item);
    }
    els.legend.replaceChildren(fragment);
  }

  /* ---------- 地图 ---------- */

  function initMap(provinces) {
    const map = L.map("map", {
      zoomControl: false,
      minZoom: 3,
      maxZoom: 11,
      zoomSnap: 0.5,
      attributionControl: true,
      preferCanvas: false,
    });
    state.map = map;

    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.control
      .scale({ position: "bottomright", imperial: false, maxWidth: 120 })
      .addTo(map);

    map.attributionControl.setPrefix(false);
    map.attributionControl.addAttribution(
      '边界 © <a href="https://datav.aliyun.com/portal/school/atlas/area_selector" target="_blank" rel="noopener noreferrer">DataV.GeoAtlas</a>',
    );

    const provinceFeatures = provinces.features.filter(
      (feature) => feature.properties.name,
    );
    const nineDashFeatures = provinces.features.filter(
      (feature) => !feature.properties.name,
    );

    if (nineDashFeatures.length) {
      L.geoJSON(
        { type: "FeatureCollection", features: nineDashFeatures },
        {
          interactive: false,
          style: {
            color: "#7f9187",
            weight: 1.2,
            opacity: 0.85,
            fill: false,
            dashArray: "4 4",
          },
        },
      ).addTo(map);
    }

    const provinceLayer = L.geoJSON(
      { type: "FeatureCollection", features: provinceFeatures },
      {
        style: {
          color: "#ad9879",
          weight: 1.2,
          opacity: 0.95,
          fillColor: "#f2e8d5",
          fillOpacity: 1,
        },
        onEachFeature(feature, layer) {
          const name = feature.properties.name;
          layer.bindTooltip(name, {
            className: "province-tip",
            sticky: true,
            direction: "top",
            opacity: 0.95,
          });
          layer.on({
            mouseover(event) {
              const target = event.target;
              target.setStyle({
                color: "#8d795c",
                weight: 1.6,
                fillColor: "#e9dcc4",
              });
              target.bringToFront();
            },
            mouseout(event) {
              provinceLayer.resetStyle(event.target);
            },
            click() {
              filterByProvince(name);
            },
          });
        },
      },
    ).addTo(map);

    map.fitBounds(MAINLAND_BOUNDS, {
      padding: [14, 14],
      animate: false,
    });

    map.on("click", () => {
      if (state.hasDetail) {
        closeDetail({ restoreFocus: false });
      }
    });
    map.on("zoomend moveend", updateMarkerActive);

    initInsetMap(provinceFeatures, nineDashFeatures);
  }

  function initInsetMap(provinceFeatures, nineDashFeatures) {
    const container = document.getElementById("inset-map");
    if (!container) return;

    const inset = L.map(container, {
      zoomControl: false,
      attributionControl: false,
      dragging: false,
      touchZoom: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false,
      tap: false,
      minZoom: 2,
      maxZoom: 5,
      zoomSnap: 0.5,
    });
    state.insetMap = inset;

    L.geoJSON(
      { type: "FeatureCollection", features: provinceFeatures },
      {
        interactive: false,
        style: {
          color: "#ad9879",
          weight: 0.9,
          opacity: 0.9,
          fillColor: "#f2e8d5",
          fillOpacity: 1,
        },
      },
    ).addTo(inset);

    if (nineDashFeatures.length) {
      L.geoJSON(
        { type: "FeatureCollection", features: nineDashFeatures },
        {
          interactive: false,
          style: {
            color: "#7f9187",
            weight: 1,
            opacity: 0.85,
            fill: false,
            dashArray: "3 3",
          },
        },
      ).addTo(inset);
    }

    inset.fitBounds(
      [
        [3.2, 105.0],
        [23.6, 123.0],
      ],
      { padding: [2, 2], animate: false },
    );
    setTimeout(() => inset.invalidateSize(), 0);
  }

  function initMarkers() {
    const cluster = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 48,
      spiderfyOnMaxZoom: true,
      disableClusteringAtZoom: 6,
      iconCreateFunction: (group) =>
        L.divIcon({
          className: "site-cluster",
          html: `<span class="site-cluster__inner">${group.getChildCount()}</span>`,
          iconSize: [34, 34],
          iconAnchor: [17, 17],
        }),
    });
    state.cluster = cluster;
    state.map.addLayer(cluster);

    for (const site of state.sites) {
      const category = categoryOf(site.category);
      const marker = L.marker([site.lat, site.lng], {
        icon: L.divIcon({
          className: "site-marker",
          html: `<span class="site-marker__dot" style="--c:${category.color}"></span>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        }),
        title: site.name,
        alt: site.name,
        keyboard: true,
        riseOnHover: true,
      });

      marker.bindTooltip(
        `<strong>${esc(site.name)}</strong><span>${esc(site.province)} · ${esc(site.city)}</span>`,
        {
          className: "site-tip",
          direction: "top",
          offset: [0, -9],
          opacity: 1,
        },
      );

      marker.on("click", () => {
        selectSite(site.id);
      });
      marker.on("keypress", (event) => {
        if (event.originalEvent?.key === "Enter") {
          selectSite(site.id);
        }
      });

      state.markerById.set(site.id, marker);
    }
  }

  /* ---------- 筛选与列表 ---------- */

  function getFilteredSites() {
    const query = state.query.trim().toLowerCase();
    return state.sites.filter((site) => {
      if (state.category !== "all" && site.category !== state.category) {
        return false;
      }
      if (state.province !== "all" && site.province !== state.province) {
        return false;
      }
      if (!query) return true;
      const haystack = [
        site.name,
        site.province,
        site.city,
        site.summary,
        site.culture,
        ...(site.tags || []),
        ...(site.heritage || []),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }

  function applyFilters({ writeHash = true, keepDetail = false } = {}) {
    state.filtered = getFilteredSites();
    state.filteredIds = new Set(state.filtered.map((site) => site.id));
    renderList();
    renderMarkers();

    els.resultCount.textContent = `${state.filtered.length} 处`;
    els.mapCaptionMeta.textContent = `${state.filtered.length} / ${state.sites.length} 处 · 点击地标查看详情`;

    if (
      state.selectedId &&
      !state.filteredIds.has(state.selectedId) &&
      !keepDetail
    ) {
      closeDetail({ restoreFocus: false, updateHash: false });
    }
    if (writeHash) syncHash();
  }

  function searchRelevance(site, query) {
    if (!query) return 0;
    const name = site.name.toLowerCase();
    if (name === query) return 0;
    if (name.startsWith(query)) return 1;
    if (name.includes(query)) return 2;
    if ((site.tags || []).some((tag) => tag.toLowerCase().includes(query))) {
      return 3;
    }
    if (
      site.province.toLowerCase().includes(query) ||
      site.city.toLowerCase().includes(query)
    ) {
      return 4;
    }
    return 5;
  }

  function renderList() {
    const query = state.query.trim().toLowerCase();
    const sorted = [...state.filtered].sort((a, b) => {
      if (query) {
        const distance = searchRelevance(a, query) - searchRelevance(b, query);
        if (distance !== 0) return distance;
      }
      return (
        a.province.localeCompare(b.province, "zh-Hans-CN") ||
        a.name.localeCompare(b.name, "zh-Hans-CN")
      );
    });

    if (!sorted.length) {
      els.siteList.innerHTML = `<li class="empty-state">没有找到匹配的站点。<br />试试更换关键词或类别。<button type="button" data-action="reset">清除筛选</button></li>`;
      return;
    }

    const fragment = document.createDocumentFragment();
    for (const site of sorted) {
      const category = categoryOf(site.category);
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "site-card";
      button.dataset.id = site.id;
      button.setAttribute(
        "aria-current",
        site.id === state.selectedId ? "true" : "false",
      );
      button.setAttribute(
        "aria-label",
        `${site.name}，${category.label}，${site.province}${site.city}`,
      );
      button.title = site.summary;
      button.innerHTML = `<span class="site-card__dot" style="--dot:${category.color}"></span><span class="site-card__body"><span class="site-card__name">${esc(site.name)}</span><span class="site-card__meta">${esc(site.province)} · ${esc(site.city)}</span></span><span class="site-card__arrow" aria-hidden="true">›</span>`;
      item.appendChild(button);
      fragment.appendChild(item);
    }
    els.siteList.replaceChildren(fragment);
  }

  function renderMarkers() {
    if (!state.cluster) return;
    state.cluster.clearLayers();
    const layers = state.filtered
      .map((site) => state.markerById.get(site.id))
      .filter(Boolean);
    state.cluster.addLayers(layers);
    updateMarkerActive();
  }

  function updateMarkerActive() {
    for (const [id, marker] of state.markerById) {
      const element = marker.getElement();
      if (element) {
        element.classList.toggle("is-active", id === state.selectedId);
      }
    }
  }

  function updateListSelection() {
    for (const card of els.siteList.querySelectorAll(".site-card")) {
      card.setAttribute(
        "aria-current",
        card.dataset.id === state.selectedId ? "true" : "false",
      );
    }
  }

  function syncChips() {
    for (const chip of els.categoryChips.querySelectorAll(".chip")) {
      const active = chip.dataset.category === state.category;
      chip.classList.toggle("is-active", active);
      chip.setAttribute("aria-pressed", active ? "true" : "false");
    }
  }

  function setCategory(key) {
    state.category = CATEGORY_BY_KEY.has(key) ? key : "all";
    syncChips();
    applyFilters();
  }

  function setProvince(name) {
    state.province = state.provinceCounts.has(name) ? name : "all";
    els.provinceSelect.value = state.province;
    applyFilters();
  }

  function filterByProvince(name) {
    if (!state.provinceCounts.has(name)) {
      toast(`${name}暂无收录站点`);
      return;
    }
    if (state.province === name) {
      setProvince("all");
      toast("已显示全部省份");
      return;
    }
    setProvince(name);
    toast(`已筛选：${name}`);
  }

  function resetFilters() {
    state.category = "all";
    state.province = "all";
    state.query = "";
    els.search.value = "";
    els.provinceSelect.value = "all";
    syncChips();
    applyFilters();
  }

  /* ---------- 详情 ---------- */

  function selectSite(id, { fly = true, focus = true } = {}) {
    const site = state.sites.find((item) => item.id === id);
    if (!site) return;

    if (!state.filteredIds.has(id)) {
      state.category = "all";
      state.province = "all";
      state.query = "";
      els.search.value = "";
      els.provinceSelect.value = "all";
      syncChips();
      applyFilters({ writeHash: false, keepDetail: true });
    }

    state.selectedId = id;
    state.hasDetail = true;
    els.mapWrap.classList.add("has-detail");
    renderDetail(site);
    els.detail.hidden = false;
    els.detail.setAttribute("aria-hidden", "false");
    updateListSelection();
    updateMarkerActive();
    centerSite(site, fly);
    if (focus) focusDetail();
    syncHash();
    if (isMobile()) closeSidebar();
  }

  function centerSite(site, animate) {
    if (!state.map) return;
    const zoom = Math.max(state.map.getZoom(), 6);
    const point = state.map.project([site.lat, site.lng], zoom);
    const size = state.map.getSize();
    let offsetX = 0;
    let offsetY = 0;

    if (state.hasDetail) {
      if (isMobile()) {
        // 详情是底部抽屉：把地标放在抽屉上方可见区域的中心。
        const detailTop = els.detail.offsetTop || size.y * 0.26;
        offsetY = Math.max(0, (size.y - detailTop) / 2);
      } else {
        // 详情在右侧：把地标放在未被遮挡区域的中心。
        offsetX = (els.detail.offsetWidth || 400) / 2;
      }
    }

    const center = state.map.unproject(
      point.add([offsetX, offsetY]),
      zoom,
    );
    if (animate && !prefersReducedMotion()) {
      state.map.flyTo(center, zoom, { duration: 0.9 });
    } else {
      state.map.setView(center, zoom, { animate: false });
    }
  }

  function focusDetail() {
    const title = els.detailScroll.querySelector("h2");
    if (title) {
      title.tabIndex = -1;
      title.focus({ preventScroll: true });
    }
  }

  function renderDetail(site) {
    const category = categoryOf(site.category);
    els.detail.style.setProperty("--accent", category.color);

    const heritage = (site.heritage || [])
      .map((item) => `<li class="heritage-item">${esc(item)}</li>`)
      .join("");
    const tags = (site.tags || [])
      .map((tag) => `<li class="tag">${esc(tag)}</li>`)
      .join("");
    const sources = (site.sources || [])
      .map(
        (source) =>
          `<li><a class="source-link" href="${esc(source.url)}" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5M19 5l-8 8M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"></path></svg><span>${esc(source.title)}</span></a></li>`,
      )
      .join("");

    els.detailScroll.innerHTML = `
      <div class="detail-badge"><span class="detail-badge__dot"></span>${esc(category.label)}</div>
      <h2>${esc(site.name)}</h2>
      <p class="detail-location"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s7-6.1 7-11a7 7 0 1 0-14 0c0 4.9 7 11 7 11Z"></path><circle cx="12" cy="10" r="2.5"></circle></svg>${esc(site.province)} · ${esc(site.city)}</p>
      <p class="detail-lead">${esc(site.summary)}</p>
      <section class="detail-section">
        <h3 class="detail-label">农事与习俗</h3>
        <p>${esc(site.culture)}</p>
      </section>
      <section class="detail-section">
        <h3 class="detail-label">遗产身份与文化价值</h3>
        <ul class="heritage-list">${heritage}</ul>
      </section>
      <section class="detail-section">
        <h3 class="detail-label">关键词</h3>
        <ul class="tag-list">${tags}</ul>
      </section>
      <section class="detail-section">
        <h3 class="detail-label">资料来源</h3>
        <ul class="source-list">${sources}</ul>
      </section>
      <div class="detail-footer">
        <span class="detail-coords">${Number(site.lat).toFixed(2)}°N · ${Number(site.lng).toFixed(2)}°E</span>
        <button class="copy-button" type="button" data-copy>复制坐标</button>
      </div>`;
    els.detailScroll.scrollTop = 0;
  }

  function closeDetail({ restoreFocus = true, updateHash = true } = {}) {
    if (!state.hasDetail) return;
    const previousId = state.selectedId;
    state.selectedId = null;
    state.hasDetail = false;
    els.detail.hidden = true;
    els.detail.setAttribute("aria-hidden", "true");
    els.mapWrap.classList.remove("has-detail");
    updateListSelection();
    updateMarkerActive();
    if (updateHash) syncHash();
    if (restoreFocus) {
      const card = previousId
        ? els.siteList.querySelector(`.site-card[data-id="${previousId}"]`)
        : null;
      if (card) {
        card.focus({ preventScroll: true });
      } else {
        const mapContainer = state.map?.getContainer();
        if (mapContainer) mapContainer.focus({ preventScroll: true });
      }
    }
  }

  /* ---------- 地址栏状态 ---------- */

  function syncHash() {
    const params = new URLSearchParams();
    if (state.selectedId) params.set("site", state.selectedId);
    if (state.category !== "all") params.set("cat", state.category);
    if (state.province !== "all") params.set("prov", state.province);
    if (state.query) params.set("q", state.query);
    const hash = params.toString();
    try {
      history.replaceState(
        null,
        "",
        hash ? `#${hash}` : `${location.pathname}${location.search}`,
      );
    } catch {
      /* file:// 等环境下忽略 */
    }
  }

  function restoreFromHash(initial = false) {
    const params = new URLSearchParams(location.hash.replace(/^#/, ""));
    const category = params.get("cat");
    const province = params.get("prov");
    state.category = CATEGORY_BY_KEY.has(category) ? category : "all";
    state.province = state.provinceCounts.has(province) ? province : "all";
    state.query = params.get("q") || "";
    els.search.value = state.query;
    els.provinceSelect.value = state.province;
    syncChips();
    applyFilters({ writeHash: false });

    const siteId = params.get("site");
    if (siteId) {
      const site = state.sites.find((item) => item.id === siteId);
      if (site) {
        selectSite(site.id, { fly: !initial, focus: !initial });
      }
    }
  }

  /* ---------- 侧栏与弹窗 ---------- */

  function syncSidebarInert() {
    const hiddenOnMobile =
      isMobile() && !els.app.classList.contains("sidebar-open");
    els.sidebar.inert = hiddenOnMobile;
  }

  function openSidebar() {
    els.app.classList.add("sidebar-open");
    els.sidebarBackdrop.hidden = false;
    els.menuButton.setAttribute("aria-expanded", "true");
    syncSidebarInert();
  }

  function closeSidebar() {
    if (!els.app.classList.contains("sidebar-open")) {
      syncSidebarInert();
      return;
    }
    els.app.classList.remove("sidebar-open");
    els.sidebarBackdrop.hidden = true;
    els.menuButton.setAttribute("aria-expanded", "false");
    syncSidebarInert();
    if (els.sidebar.contains(document.activeElement)) {
      els.menuButton.focus({ preventScroll: true });
    }
  }

  function toggleSidebar() {
    if (els.app.classList.contains("sidebar-open")) {
      closeSidebar();
    } else {
      openSidebar();
    }
  }

  function openAbout() {
    lastModalFocus = document.activeElement;
    els.aboutModal.hidden = false;
    els.aboutModal.setAttribute("aria-hidden", "false");
    const close = els.aboutModal.querySelector(".modal-close");
    close?.focus({ preventScroll: true });
  }

  function closeAbout() {
    if (els.aboutModal.hidden) return;
    els.aboutModal.hidden = true;
    els.aboutModal.setAttribute("aria-hidden", "true");
    if (lastModalFocus instanceof HTMLElement) {
      lastModalFocus.focus({ preventScroll: true });
    }
  }

  function trapModalFocus(event) {
    if (event.key !== "Tab" || els.aboutModal.hidden) return;
    const focusables = [
      ...els.aboutModal.querySelectorAll(
        'button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      ),
    ].filter((element) => !element.hasAttribute("disabled"));
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function toast(message) {
    els.toast.textContent = message;
    els.toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      els.toast.hidden = true;
    }, 1900);
  }

  async function copyCoordinates(button) {
    const text = button
      .closest(".detail-footer")
      ?.querySelector(".detail-coords")?.textContent;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast("坐标已复制");
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand("copy");
        toast("坐标已复制");
      } catch {
        toast("复制失败，请手动选择坐标");
      } finally {
        textarea.remove();
      }
    }
  }

  /* ---------- 事件 ---------- */

  function bindEvents() {
    els.search.addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        state.query = els.search.value.trim();
        applyFilters();
      }, 120);
    });

    els.search.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        els.search.value = "";
        state.query = "";
        applyFilters();
        els.search.blur();
      }
    });

    els.resetFilters.addEventListener("click", resetFilters);
    els.categoryChips.addEventListener("click", (event) => {
      const chip = event.target.closest("[data-category]");
      if (chip) setCategory(chip.dataset.category);
    });
    els.provinceSelect.addEventListener("change", () => {
      setProvince(els.provinceSelect.value);
    });

    els.siteList.addEventListener("click", (event) => {
      const reset = event.target.closest('[data-action="reset"]');
      if (reset) {
        resetFilters();
        return;
      }
      const card = event.target.closest(".site-card");
      if (card) selectSite(card.dataset.id);
    });

    els.detailClose.addEventListener("click", () => closeDetail());
    els.detailScroll.addEventListener("click", (event) => {
      const copy = event.target.closest("[data-copy]");
      if (copy) copyCoordinates(copy);
    });

    els.menuButton.addEventListener("click", toggleSidebar);
    els.sidebarBackdrop.addEventListener("click", closeSidebar);

    els.resetView.addEventListener("click", () => {
      state.map?.flyToBounds(MAINLAND_BOUNDS, {
        padding: [14, 14],
        duration: prefersReducedMotion() ? 0 : 0.8,
      });
      if (isMobile()) closeSidebar();
    });

    for (const button of [els.aboutButton, els.aboutButtonMap]) {
      button.addEventListener("click", openAbout);
    }
    els.aboutModal.addEventListener("click", (event) => {
      if (event.target.closest("[data-close-modal]")) {
        closeAbout();
      }
    });
    els.aboutModal.addEventListener("keydown", trapModalFocus);

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (!els.aboutModal.hidden) {
          closeAbout();
          return;
        }
        if (state.hasDetail) {
          closeDetail();
          return;
        }
        if (els.app.classList.contains("sidebar-open")) {
          closeSidebar();
          return;
        }
      }

      if (
        event.key === "/" &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey
      ) {
        const target = event.target;
        const typing =
          target instanceof HTMLElement &&
          (target.tagName === "INPUT" ||
            target.tagName === "TEXTAREA" ||
            target.tagName === "SELECT" ||
            target.isContentEditable);
        if (!typing) {
          event.preventDefault();
          els.search.focus();
          els.search.select();
        }
      }
    });

    window.addEventListener("hashchange", () => {
      const params = new URLSearchParams(location.hash.replace(/^#/, ""));
      if (!params.get("site") && state.hasDetail) {
        closeDetail({ restoreFocus: false, updateHash: false });
      }
      restoreFromHash(false);
    });

    window.addEventListener("resize", () => {
      if (!isMobile()) {
        closeSidebar();
      }
      syncSidebarInert();
      state.map?.invalidateSize();
      state.insetMap?.invalidateSize();
    });

    els.mapWrap.addEventListener("transitionend", () => {
      state.map?.invalidateSize();
    });
  }

  // 供页面内嵌、调试或二次开发使用的只读/便捷入口。
  window.FarmingCultureAtlas = {
    get sites() {
      return state.sites;
    },
    get filtered() {
      return state.filtered;
    },
    get map() {
      return state.map;
    },
    selectSite,
    setCategory,
    setProvince,
    resetFilters,
    closeDetail,
  };

  init().catch((error) => {
    console.error(error);
    els.mapCaptionMeta.textContent = "数据载入失败";
    els.siteList.innerHTML = `<li class="empty-state">数据载入失败：${esc(error.message)}<br />请通过 <code>python3 web/server.py</code> 访问，而不是直接打开 HTML 文件。</li>`;
  });
})();
