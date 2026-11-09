// DOM controller owned by the React assessment page.
export function installLayers(ctx) {
  const {
    document,
    L,
    ColorAdjustments
  } = ctx;
  ctx.layerIdentity = function layerIdentity(item, index) {
    return item.source_id || `${item.kind}:${item.name}:${index}`;
  };
  ctx.componentKey = function componentKey(overlay, feature) {
    const properties = feature.properties || {};
    return overlay.item.kind === "prediction" ? `Kết quả Y = ${properties.Y ?? "Chưa có"}` : String(properties.layer || feature.geometry?.type || "Không phân lớp");
  };
  ctx.componentLabel = function componentLabel(group) {
    return group.name === "Kết quả Y = Chưa có" ? "Chưa có dữ liệu" : group.name;
  };
  ctx.parcelPopupName = function parcelPopupName(overlay, feature) {
    const properties = feature.properties || {};
    const keys = ['tenlodat', 'attr:tenlodat', 'code', 'result_key', 'grid_id', overlay.item.data.join_summary?.layer_join];
    const value = keys.map(key => properties[key]).find(value => value != null && ['string', 'number'].includes(typeof value) && String(value).trim());
    return value == null ? 'Lô đất chưa có tên' : String(value);
  };
  ctx.managedStyle = function managedStyle(overlay, feature, adjustColors = true) {
    const group = overlay.groups.get(ctx.componentKey(overlay, feature));
    const style = {
      ...overlay.style,
      ...group?.style
    };
    const properties = feature.properties || {};
    const baseColor = style.color ?? (overlay.item.kind === "prediction" ? "#334155" : properties.color || overlay.color);
    const fillColor = style.fillColor ?? properties.fillColor ?? properties.color ?? overlay.color;
    return {
      color: adjustColors ? ctx.adjustedLayerColor(overlay, baseColor) : baseColor,
      fillColor: adjustColors ? ctx.adjustedLayerColor(overlay, fillColor) : fillColor,
      weight: style.weight,
      opacity: overlay.opacity,
      fillOpacity: (style.fillOpacity ?? properties.fillOpacity ?? 0) * overlay.opacity,
      radius: style.radius,
      dashArray: style.dashArray || null
    };
  };
  ctx.adjustedLayerColor = function adjustedLayerColor(overlay, color) {
    if (!overlay.colorCache.has(color)) overlay.colorCache.set(color, ColorAdjustments.apply(color, overlay.adjustments));
    return overlay.colorCache.get(color);
  };
  ctx.refreshManagedLayer = function refreshManagedLayer(overlay) {
    for (const record of overlay.records) {
      const group = overlay.groups.get(record.group);
      const style = ctx.managedStyle(overlay, record.feature);
      const settings = { ...overlay.style, ...group?.style };
      ctx.translateManagedRecord(overlay, record, settings.east ?? 0, settings.north ?? 0);
      record.layer.setStyle(style);
      if (record.layer.setRadius) record.layer.setRadius(style.radius);
      if (group.visible && !overlay.layer.hasLayer(record.layer)) overlay.layer.addLayer(record.layer);
      if (!group.visible && overlay.layer.hasLayer(record.layer)) overlay.layer.removeLayer(record.layer);
    }
    overlay.bounds = overlay.layer.getBounds();
  };
  // Display offsets in ground metres, derived from original Leaflet coordinates.
  // Never rewrite source GeoJSON or repeatedly shift already translated positions.
  ctx.translateManagedRecord = function translateManagedRecord(overlay, record, east, north) {
    const key = `${east}:${north}`;
    if (record.translationKey === key || (!record.translationBases && !east && !north)) return;
    if (!record.translationBases) {
      record.translationBases = [];
      const collect = layer => {
        if (layer.getLatLngs) record.translationBases.push({ layer, coordinates: layer.getLatLngs(), point: false });
        else if (layer.getLatLng) record.translationBases.push({ layer, coordinates: layer.getLatLng(), point: true });
        else if (layer.eachLayer) layer.eachLayer(collect);
      };
      collect(record.layer);
    }
    const scale = Math.max(0.01, Math.cos(overlay.translationLatitude * Math.PI / 180));
    const shift = value => {
      if (Array.isArray(value)) return value.map(shift);
      const point = L.CRS.EPSG3857.project(value);
      return L.CRS.EPSG3857.unproject(L.point(point.x + east / scale, point.y + north / scale));
    };
    for (const base of record.translationBases) {
      if (base.point) base.layer.setLatLng(shift(base.coordinates));
      else base.layer.setLatLngs(shift(base.coordinates));
    }
    record.translationKey = key;
  };
  ctx.fitManagedBounds = function fitManagedBounds(bounds) {
    if (!bounds.isValid()) return;
    if (ctx.$("map-panel").hidden) {
      ctx.pendingMapBounds = bounds;
      return;
    }
    const right = !ctx.$("layer-inspector").hidden && ctx.map.getSize().x > 850 ? 410 : 24;
    ctx.map.fitBounds(bounds, {
      paddingTopLeft: [24, 24],
      paddingBottomRight: [right, 24],
      maxZoom: 18
    });
  };
  ctx.fitAllManagedLayers = function fitAllManagedLayers() {
    const bounds = L.latLngBounds();
    for (const overlay of ctx.overlays) {
      if (overlay.visible && overlay.layer.getLayers().length) bounds.extend(overlay.layer.getBounds());
    }
    ctx.fitManagedBounds(bounds);
  };
  ctx.renderManagedLayers = function renderManagedLayers(items, savedLayers = null) {
    const previous = new Map((savedLayers || ctx.overlays).map(overlay => [overlay.id, overlay]));
    for (const overlay of ctx.overlays) ctx.map.removeLayer(overlay.layer);
    ctx.overlays = [];
    ctx.$("layer-list").replaceChildren();
    for (const [index, item] of items.entries()) {
      const id = ctx.layerIdentity(item, index);
      const saved = previous.get(id);
      const overlay = {
        id,
        item,
        color: saved?.color || ctx.layerPalette[index % ctx.layerPalette.length],
        visible: saved?.visible ?? true,
        opacity: saved?.opacity ?? 1,
        style: saved?.style || {
          weight: item.kind === "prediction" ? 1 : 2,
          radius: 1,
          fillOpacity: 0,
          dashArray: ""
        },
        groups: new Map(),
        records: [],
        adjustments: ColorAdjustments.normalize(saved?.adjustments),
        colorCache: new Map()
      };
      for (const feature of item.data.features) {
        const key = ctx.componentKey(overlay, feature);
        if (!overlay.groups.has(key)) {
          const oldGroup = saved?.groups.get(key);
          overlay.groups.set(key, {
            name: key,
            count: 0,
            visible: oldGroup?.visible ?? true,
            style: oldGroup?.style || {}
          });
        }
        overlay.groups.get(key).count++;
      }
      overlay.layer = L.geoJSON(item.data, {
        style: feature => ctx.managedStyle(overlay, feature),
        pointToLayer: (feature, latlng) => L.circleMarker(latlng, ctx.managedStyle(overlay, feature)),
        onEachFeature: (feature, layer) => {
          const record = {
            feature,
            layer,
            group: ctx.componentKey(overlay, feature),
            index: overlay.records.length
          };
          overlay.records.push(record);
          if (item.kind === 'prediction') {
            const name = document.createElement('span');
            name.className = 'parcel-popup-name';
            name.textContent = ctx.parcelPopupName(overlay, feature);
            layer.bindPopup(name, {
              className: 'parcel-name-popup',
              minWidth: 70,
              maxWidth: 220,
              autoPan: false
            });
          }
          layer.on("click", () => {
            ctx.selectManagedLayer(overlay.id, record.group, item.kind !== 'prediction');
            ctx.inspectFeature(overlay, record);
          });
        }
      });
      overlay.bounds = overlay.layer.getBounds();
      overlay.translationLatitude = overlay.bounds.isValid() ? overlay.bounds.getCenter().lat : 0;
      ctx.refreshManagedLayer(overlay);
      if (overlay.visible) overlay.layer.addTo(ctx.map);
      ctx.overlays.push(overlay);
      ctx.renderManagedCard(overlay, index);
    }
    ctx.$("layer-count").textContent = String(items.length);
    ctx.$("fit-all-layers").disabled = !items.length;
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "empty-layers";
      empty.textContent = "Chưa có layer. Thêm file bên dưới rồi nhấn Hiển thị trên bản đồ.";
      ctx.$("layer-list").append(empty);
    }
    if (ctx.overlays.some(overlay => overlay.id === ctx.selectedLayerId)) ctx.selectManagedLayer(ctx.selectedLayerId, ctx.inspectorScope);else ctx.closeLayerInspector();
    ctx.fitAllManagedLayers();
  };
  ctx.renderManagedCard = function renderManagedCard(overlay, index) {
    const card = document.createElement("div");
    card.className = "layer-card";
    card.dataset.layerId = overlay.id;
    const heading = document.createElement("div");
    heading.className = "layer-card-heading";
    const visible = document.createElement("input");
    visible.type = "checkbox";
    visible.checked = overlay.visible;
    visible.id = `layer-visible-${index}`;
    visible.setAttribute("aria-label", `Hiển thị ${overlay.item.name}`);
    visible.addEventListener("change", () => {
      overlay.visible = visible.checked;
      if (visible.checked) overlay.layer.addTo(ctx.map);else ctx.map.removeLayer(overlay.layer);
    });
    const name = document.createElement("button");
    name.type = "button";
    name.className = "layer-select";
    name.textContent = overlay.item.name;
    name.title = "Mở thông tin thành phần và bảng màu";
    name.addEventListener("click", () => ctx.selectManagedLayer(overlay.id));
    heading.append(visible, name);
    const meta = document.createElement("p");
    meta.className = "layer-meta";
    meta.textContent = `${overlay.item.crs} · ${overlay.records.length.toLocaleString("vi-VN")} đối tượng · ${overlay.groups.size} thành phần`;
    const label = document.createElement("label");
    label.className = "opacity-label";
    label.htmlFor = `layer-opacity-${index}`;
    label.textContent = "Độ đậm cả layer";
    const output = document.createElement("output");
    output.textContent = `${Math.round(overlay.opacity * 100)}%`;
    label.append(output);
    const slider = document.createElement("input");
    slider.type = "range";
    slider.id = label.htmlFor;
    slider.min = "0";
    slider.max = "100";
    slider.value = String(Math.round(overlay.opacity * 100));
    slider.addEventListener("input", () => {
      overlay.opacity = Number(slider.value) / 100;
      output.textContent = `${slider.value}%`;
      ctx.refreshManagedLayer(overlay);
    });
    const zoom = document.createElement("button");
    zoom.type = "button";
    zoom.className = "cad-action";
    zoom.textContent = "Đến layer";
    zoom.addEventListener("click", () => ctx.fitManagedBounds(overlay.bounds));
    card.append(heading, meta, label, slider, zoom);
    const source = [...ctx.cadFiles, ...ctx.predictionFiles].find(entry => entry.id === overlay.item.source_id);
    if (source) card.append(ctx.sourceRemoveButton(source, overlay.item.kind === "base" ? "cad" : "prediction"));
    ctx.$("layer-list").append(card);
  };
  ctx.closeLayerInspector = function closeLayerInspector() {
    ctx.selectedLayerId = null;
    ctx.inspectorScope = "";
    ctx.$("layer-inspector").hidden = true;
    for (const card of document.querySelectorAll(".layer-card")) card.classList.remove("selected");
    ctx.window.dispatchEvent(new Event('assistant-layer-change'));
  };
  ctx.selectManagedLayer = function selectManagedLayer(id, scope = "", zoom = true) {
    const overlay = ctx.overlays.find(entry => entry.id === id);
    if (!overlay) return;
    const changed = ctx.selectedLayerId !== id;
    const opening = ctx.$("layer-inspector").hidden || changed;
    ctx.selectedLayerId = id;
    ctx.inspectorScope = overlay.groups.has(scope) ? scope : "";
    ctx.$("layer-inspector").hidden = false;
    ctx.$("inspector-title").textContent = overlay.item.name;
    const counts = new Map();
    for (const record of overlay.records) counts.set(record.feature.geometry.type, (counts.get(record.feature.geometry.type) || 0) + 1);
    ctx.$("inspector-meta").textContent = `${overlay.item.crs} · ${overlay.records.length.toLocaleString("vi-VN")} đối tượng, ` + [...counts].map(([type, count]) => `${type}: ${count}`).join(" · ");
    ctx.$("inspector-warnings").textContent = Object.entries(overlay.item.data.warnings || {}).map(([reason, count]) => `${reason}: ${count}`).join(", ");
    const scopes = ctx.$("style-scope");
    scopes.replaceChildren(new Option("Toàn bộ layer", ""));
    for (const group of overlay.groups.values()) scopes.append(new Option(`${ctx.componentLabel(group)} (${group.count})`, group.name));
    scopes.value = ctx.inspectorScope;
    if (changed) {
      ctx.$("component-search").value = "";
      ctx.$("attribute-search").value = "";
    }
    ctx.componentPage = 0;
    ctx.attributePage = 0;
    ctx.$("feature-details").replaceChildren();
    for (const card of document.querySelectorAll(".layer-card")) card.classList.toggle("selected", card.dataset.layerId === id);
    ctx.renderStyleEditor(overlay);
    ctx.renderComponents(overlay);
    ctx.renderAttributes(overlay);
    ctx.renderColorAdjustments(overlay);
    if (opening && zoom) ctx.fitManagedBounds(overlay.bounds);
    ctx.window.dispatchEvent(new Event('assistant-layer-change'));
  };
  ctx.currentOverlay = function currentOverlay() {
    return ctx.overlays.find(overlay => overlay.id === ctx.selectedLayerId);
  };
  ctx.activeStyle = function activeStyle(overlay) {
    return ctx.inspectorScope ? overlay.groups.get(ctx.inspectorScope).style : overlay.style;
  };
  ctx.renderStyleEditor = function renderStyleEditor(overlay) {
    const style = ctx.activeStyle(overlay);
    const first = overlay.records.find(record => !ctx.inspectorScope || record.group === ctx.inspectorScope);
    const effective = first ? ctx.managedStyle(overlay, first.feature, false) : {
      color: overlay.color,
      fillColor: overlay.color,
      weight: 2,
      radius: 1,
      fillOpacity: 0
    };
    ctx.$("style-source").checked = style.color == null && style.fillColor == null;
    ctx.$("style-stroke").value = effective.color;
    ctx.$("style-fill").value = effective.fillColor;
    for (const [id, value, suffix] of [["style-weight", effective.weight, " px"], ["style-radius", effective.radius, " px"], ["style-fill-opacity", Math.round((style.fillOpacity ?? overlay.style.fillOpacity ?? first?.feature.properties?.fillOpacity ?? 0) * 100), "%"]]) {
      ctx.$(id).value = value;
      ctx.$(`${id}-value`).textContent = `${value}${suffix}`;
    }
    ctx.$("style-dash").value = style.dashArray ?? overlay.style.dashArray ?? "";
    for (const key of ['east', 'north']) if (ctx.$(`style-${key}`)) ctx.$(`style-${key}`).value = style[key] ?? overlay.style[key] ?? 0;
  };
  ctx.changeStyle = function changeStyle(values) {
    const overlay = ctx.currentOverlay();
    if (!overlay) return;
    Object.assign(ctx.activeStyle(overlay), values);
    ctx.refreshManagedLayer(overlay);
    ctx.renderStyleEditor(overlay);
    ctx.renderComponents(overlay);
  };
  ctx.pager = function pager(container, page, total, onPage) {
    container.replaceChildren();
    const pages = Math.max(1, Math.ceil(total / 50));
    const previous = document.createElement("button");
    previous.type = "button";
    previous.textContent = "Trước";
    previous.disabled = page <= 0;
    const next = document.createElement("button");
    next.type = "button";
    next.textContent = "Sau";
    next.disabled = page + 1 >= pages;
    previous.addEventListener("click", () => onPage(page - 1));
    next.addEventListener("click", () => onPage(page + 1));
    const label = document.createElement("span");
    label.textContent = `${page + 1}/${pages} · ${total.toLocaleString("vi-VN")} mục`;
    container.append(previous, label, next);
  };
  ctx.renderComponents = function renderComponents(overlay) {
    const query = ctx.$("component-search").value.toLocaleLowerCase("vi-VN");
    const groups = [...overlay.groups.values()].filter(group => ctx.componentLabel(group).toLocaleLowerCase("vi-VN").includes(query));
    ctx.componentPage = Math.min(ctx.componentPage, Math.max(0, Math.ceil(groups.length / 50) - 1));
    const list = ctx.$("component-list");
    list.replaceChildren();
    for (const group of groups.slice(ctx.componentPage * 50, (ctx.componentPage + 1) * 50)) {
      const row = document.createElement("div");
      row.className = "component-row";
      const toggle = document.createElement("input");
      toggle.type = "checkbox";
      toggle.checked = group.visible;
      toggle.setAttribute("aria-label", `Hiển thị thành phần ${ctx.componentLabel(group)}`);
      toggle.addEventListener("change", () => {
        group.visible = toggle.checked;
        ctx.refreshManagedLayer(overlay);
      });
      const name = document.createElement("button");
      name.type = "button";
      name.textContent = `${ctx.componentLabel(group)} (${group.count})`;
      name.title = 'Mở chatbot cho thành phần này';
      name.addEventListener("click", () => {
        ctx.selectManagedLayer(overlay.id, group.name, false);
        ctx.window.dispatchEvent(new Event('assistant-open'));
      });
      const color = document.createElement("input");
      color.type = "color";
      color.setAttribute("aria-label", `Màu thành phần ${ctx.componentLabel(group)}`);
      const first = overlay.records.find(record => record.group === group.name);
      color.value = ctx.managedStyle(overlay, first.feature, false).color;
      color.addEventListener("input", () => {
        group.style.color = color.value;
        group.style.fillColor = color.value;
        ctx.refreshManagedLayer(overlay);
        ctx.renderStyleEditor(overlay);
      });
      row.append(toggle, name, color);
      list.append(row);
    }
    ctx.pager(ctx.$("component-pager"), ctx.componentPage, groups.length, page => {
      ctx.componentPage = page;
      ctx.renderComponents(overlay);
    });
  };
  ctx.attributeText = function attributeText(value) {
    return value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);
  };
  ctx.inspectFeature = function inspectFeature(overlay, record) {
    const details = ctx.$("feature-details");
    details.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = `Đối tượng #${record.index + 1} · ${record.feature.geometry.type}`;
    const list = document.createElement("dl");
    for (const [key, value] of Object.entries(record.feature.properties || {})) {
      const term = document.createElement("dt");
      term.textContent = key;
      const text = document.createElement("dd");
      text.textContent = ctx.attributeText(value);
      list.append(term, text);
    }
    details.append(heading, list);
  };
  ctx.renderAttributes = function renderAttributes(overlay) {
    const query = ctx.$("attribute-search").value.toLocaleLowerCase("vi-VN");
    const records = overlay.records.filter(record => (!ctx.inspectorScope || record.group === ctx.inspectorScope) && (!query || Object.values(record.feature.properties || {}).some(value => ctx.attributeText(value).toLocaleLowerCase("vi-VN").includes(query))));
    ctx.attributePage = Math.min(ctx.attributePage, Math.max(0, Math.ceil(records.length / 50) - 1));
    const columns = [...new Set(records.flatMap(record => Object.keys(record.feature.properties || {})))];
    const table = ctx.$("attribute-table");
    table.replaceChildren();
    const head = table.createTHead().insertRow();
    for (const name of ["#", "Hình học", ...columns]) {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = name;
      head.append(th);
    }
    const body = table.createTBody();
    for (const record of records.slice(ctx.attributePage * 50, (ctx.attributePage + 1) * 50)) {
      const row = body.insertRow();
      const cell = row.insertCell();
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = String(record.index + 1);
      button.setAttribute("aria-label", `Xem đối tượng ${record.index + 1}`);
      button.addEventListener("click", () => {
        ctx.inspectFeature(overlay, record);
        const bounds = record.layer.getBounds ? record.layer.getBounds() : L.latLngBounds([record.layer.getLatLng(), record.layer.getLatLng()]);
        ctx.fitManagedBounds(bounds);
      });
      cell.append(button);
      for (const value of [record.feature.geometry.type, ...columns.map(name => record.feature.properties?.[name])]) {
        const td = row.insertCell();
        td.textContent = ctx.attributeText(value);
        td.title = ctx.attributeText(value);
      }
    }
    ctx.pager(ctx.$("attribute-pager"), ctx.attributePage, records.length, page => {
      ctx.attributePage = page;
      ctx.renderAttributes(overlay);
    });
  };
  ctx.renderColorAdjustments = function renderColorAdjustments(overlay) {
    for (const key of Object.keys(ColorAdjustments.defaults)) {
      ctx.$(`adjust-${key}`).value = overlay.adjustments[key];
      ctx.$(`adjust-${key}-value`).textContent = `${overlay.adjustments[key]}${key === "hue" ? "°" : "%"}`;
    }
  };
  ctx.updateColorAdjustments = function updateColorAdjustments(overlay, settings) {
    overlay.adjustments = ColorAdjustments.normalize(settings);
    overlay.colorCache.clear();
    ctx.refreshManagedLayer(overlay);
    ctx.renderColorAdjustments(overlay);
  };
  ctx.selectedLayerId = null;
  ctx.inspectorScope = "";
  ctx.attributePage = 0;
  ctx.componentPage = 0;
  ctx.layerPalette = ["#0b8753", "#d97706", "#2563eb", "#9333ea", "#e11d48", "#ffffff"];
  ctx.$("inspector-close").addEventListener("click", ctx.closeLayerInspector);
  ctx.$("fit-all-layers").addEventListener("click", ctx.fitAllManagedLayers);
  ctx.$("style-scope").addEventListener("change", () => {
    ctx.inspectorScope = ctx.$("style-scope").value;
    ctx.attributePage = 0;
    const overlay = ctx.currentOverlay();
    if (overlay) {
      ctx.renderStyleEditor(overlay);
      ctx.renderAttributes(overlay);
    }
  });
  ctx.$("style-stroke").addEventListener("input", () => ctx.changeStyle({
    color: ctx.$("style-stroke").value
  }));
  ctx.$("style-fill").addEventListener("input", () => ctx.changeStyle({
    fillColor: ctx.$("style-fill").value
  }));
  ctx.$("style-source").addEventListener("change", () => {
    const overlay = ctx.currentOverlay();
    if (!overlay) return;
    const style = ctx.activeStyle(overlay);
    if (ctx.$("style-source").checked) {
      delete style.color;
      delete style.fillColor;
    } else {
      style.color = ctx.$("style-stroke").value;
      style.fillColor = ctx.$("style-fill").value;
    }
    ctx.refreshManagedLayer(overlay);
    ctx.renderStyleEditor(overlay);
    ctx.renderComponents(overlay);
  });
  for (const [id, key, divisor] of [["style-weight", "weight", 1], ["style-radius", "radius", 1], ["style-fill-opacity", "fillOpacity", 100]]) {
    ctx.$(id).addEventListener("input", () => ctx.changeStyle({
      [key]: Number(ctx.$(id).value) / divisor
    }));
  }
  ctx.$("style-dash").addEventListener("change", () => ctx.changeStyle({
    dashArray: ctx.$("style-dash").value
  }));
  for (const key of ['east', 'north']) ctx.$(`style-${key}`)?.addEventListener('change', () => {
    const input = ctx.$(`style-${key}`);
    const value = Number(input.value);
    if (input.value.trim() && Number.isFinite(value) && Math.abs(value) <= 100000) ctx.changeStyle({ [key]: value });
    else ctx.renderStyleEditor(ctx.currentOverlay());
  });
  ctx.$("style-reset").addEventListener("click", () => {
    const overlay = ctx.currentOverlay();
    if (!overlay) return;
    if (ctx.inspectorScope) {
      overlay.groups.get(ctx.inspectorScope).style = {};
    } else {
      overlay.style = {
        weight: overlay.item.kind === "prediction" ? 1 : 2,
        radius: 1,
        fillOpacity: 0,
        dashArray: ""
      };
      for (const group of overlay.groups.values()) group.style = {};
      overlay.adjustments = {
        ...ColorAdjustments.defaults
      };
      overlay.colorCache.clear();
    }
    ctx.refreshManagedLayer(overlay);
    ctx.renderStyleEditor(overlay);
    ctx.renderComponents(overlay);
    ctx.renderColorAdjustments(overlay);
  });
  ctx.$("component-search").addEventListener("input", () => {
    ctx.componentPage = 0;
    const overlay = ctx.currentOverlay();
    if (overlay) ctx.renderComponents(overlay);
  });
  ctx.$("attribute-search").addEventListener("input", () => {
    ctx.attributePage = 0;
    const overlay = ctx.currentOverlay();
    if (overlay) ctx.renderAttributes(overlay);
  });
  for (const color of ctx.layerPalette) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "palette-swatch";
    button.style.backgroundColor = color;
    button.setAttribute("aria-label", `Chọn màu ${color}`);
    button.addEventListener("click", () => {
      ctx.changeStyle({
        color,
        fillColor: color
      });
      const overlay = ctx.currentOverlay();
      if (overlay) ctx.renderComponents(overlay);
    });
    ctx.$("style-palette").append(button);
  }
  for (const key of Object.keys(ColorAdjustments.defaults)) {
    ctx.$(`adjust-${key}`).addEventListener("input", () => {
      const overlay = ctx.currentOverlay();
      if (!overlay) return;
      ctx.updateColorAdjustments(overlay, {
        ...overlay.adjustments,
        [key]: Number(ctx.$(`adjust-${key}`).value)
      });
    });
  }
  ctx.$("adjust-reset").addEventListener("click", () => {
    const overlay = ctx.currentOverlay();
    if (overlay) ctx.updateColorAdjustments(overlay, ColorAdjustments.defaults);
  });
}
