// Source identities, not list positions, own styles and visibility across reloads.
let selectedLayerId = null;
let inspectorScope = "";
let attributePage = 0;
let componentPage = 0;
const layerPalette = ["#0b8753", "#d97706", "#2563eb", "#9333ea", "#e11d48", "#ffffff"];

function layerIdentity(item, index) {
    return item.source_id || `${item.kind}:${item.name}:${index}`;
}

function componentKey(overlay, feature) {
    const properties = feature.properties || {};
    return overlay.item.kind === "prediction"
        ? `Kết quả Y = ${properties.Y ?? "Chưa có"}`
        : String(properties.layer || feature.geometry?.type || "Không phân lớp");
}

function managedStyle(overlay, feature, adjustColors = true) {
    const group = overlay.groups.get(componentKey(overlay, feature));
    const style = { ...overlay.style, ...group?.style };
    const properties = feature.properties || {};
    const baseColor = style.color ?? (overlay.item.kind === "prediction" ? "#334155" : properties.color || overlay.color);
    const fillColor = style.fillColor ?? properties.fillColor ?? properties.color ?? overlay.color;
    return {
        color: adjustColors ? adjustedLayerColor(overlay, baseColor) : baseColor,
        fillColor: adjustColors ? adjustedLayerColor(overlay, fillColor) : fillColor,
        weight: style.weight, opacity: overlay.opacity,
        fillOpacity: (style.fillOpacity ?? properties.fillOpacity ?? 0.28) * overlay.opacity,
        radius: style.radius, dashArray: style.dashArray || null,
    };
}

function adjustedLayerColor(overlay, color) {
    if (!overlay.colorCache.has(color)) overlay.colorCache.set(color, ColorAdjustments.apply(color, overlay.adjustments));
    return overlay.colorCache.get(color);
}

function refreshManagedLayer(overlay) {
    for (const record of overlay.records) {
        const group = overlay.groups.get(record.group);
        const style = managedStyle(overlay, record.feature);
        record.layer.setStyle(style);
        if (record.layer.setRadius) record.layer.setRadius(style.radius);
        if (group.visible && !overlay.layer.hasLayer(record.layer)) overlay.layer.addLayer(record.layer);
        if (!group.visible && overlay.layer.hasLayer(record.layer)) overlay.layer.removeLayer(record.layer);
    }
}

function fitManagedBounds(bounds) {
    if (!bounds.isValid()) return;
    if ($("map-panel").hidden) { pendingMapBounds = bounds; return; }
    const right = !$("layer-inspector").hidden && map.getSize().x > 850 ? 410 : 24;
    map.fitBounds(bounds, { paddingTopLeft: [24, 24], paddingBottomRight: [right, 24], maxZoom: 18 });
}

function fitAllManagedLayers() {
    const bounds = L.latLngBounds();
    for (const overlay of overlays) {
        if (overlay.visible && overlay.layer.getLayers().length) bounds.extend(overlay.layer.getBounds());
    }
    fitManagedBounds(bounds);
}

function renderManagedLayers(items, savedLayers = null) {
    const previous = new Map((savedLayers || overlays).map((overlay) => [overlay.id, overlay]));
    for (const overlay of overlays) map.removeLayer(overlay.layer);
    overlays = [];
    $("layer-list").replaceChildren();
    for (const [index, item] of items.entries()) {
        const id = layerIdentity(item, index);
        const saved = previous.get(id);
        const overlay = {
            id, item, color: saved?.color || layerPalette[index % layerPalette.length],
            visible: saved?.visible ?? true, opacity: saved?.opacity ?? 1,
            style: saved?.style || { weight: item.kind === "prediction" ? 1 : 2, radius: 5, dashArray: "" },
            groups: new Map(), records: [],
            adjustments: ColorAdjustments.normalize(saved?.adjustments), colorCache: new Map(),
        };
        for (const feature of item.data.features) {
            const key = componentKey(overlay, feature);
            if (!overlay.groups.has(key)) {
                const oldGroup = saved?.groups.get(key);
                overlay.groups.set(key, { name: key, count: 0, visible: oldGroup?.visible ?? true, style: oldGroup?.style || {} });
            }
            overlay.groups.get(key).count++;
        }
        overlay.layer = L.geoJSON(item.data, {
            style: (feature) => managedStyle(overlay, feature),
            pointToLayer: (feature, latlng) => L.circleMarker(latlng, managedStyle(overlay, feature)),
            onEachFeature: (feature, layer) => {
                const record = { feature, layer, group: componentKey(overlay, feature), index: overlay.records.length };
                overlay.records.push(record);
                layer.on("click", () => {
                    selectManagedLayer(overlay.id, record.group);
                    inspectFeature(overlay, record);
                });
            },
        });
        overlay.bounds = overlay.layer.getBounds();
        refreshManagedLayer(overlay);
        if (overlay.visible) overlay.layer.addTo(map);
        overlays.push(overlay);
        renderManagedCard(overlay, index);
    }
    $("layer-count").textContent = String(items.length);
    $("fit-all-layers").disabled = !items.length;
    if (!items.length) {
        const empty = document.createElement("p"); empty.className = "empty-layers";
        empty.textContent = "Chưa có layer. Thêm file bên dưới rồi nhấn Hiển thị trên bản đồ.";
        $("layer-list").append(empty);
    }
    if (overlays.some((overlay) => overlay.id === selectedLayerId)) selectManagedLayer(selectedLayerId, inspectorScope);
    else closeLayerInspector();
    fitAllManagedLayers();
}

function renderManagedCard(overlay, index) {
    const card = document.createElement("div"); card.className = "layer-card"; card.dataset.layerId = overlay.id;
    const heading = document.createElement("div"); heading.className = "layer-card-heading";
    const visible = document.createElement("input"); visible.type = "checkbox"; visible.checked = overlay.visible;
    visible.id = `layer-visible-${index}`; visible.setAttribute("aria-label", `Hiển thị ${overlay.item.name}`);
    visible.addEventListener("change", () => {
        overlay.visible = visible.checked;
        if (visible.checked) overlay.layer.addTo(map); else map.removeLayer(overlay.layer);
    });
    const name = document.createElement("button"); name.type = "button"; name.className = "layer-select";
    name.textContent = overlay.item.name; name.title = "Mở thông tin thành phần và bảng màu";
    name.addEventListener("click", () => selectManagedLayer(overlay.id));
    heading.append(visible, name);
    const meta = document.createElement("p"); meta.className = "layer-meta";
    meta.textContent = `${overlay.item.crs} · ${overlay.records.length.toLocaleString("vi-VN")} đối tượng · ${overlay.groups.size} thành phần`;
    const label = document.createElement("label"); label.className = "opacity-label"; label.htmlFor = `layer-opacity-${index}`;
    label.textContent = "Độ đậm cả layer";
    const output = document.createElement("output"); output.textContent = `${Math.round(overlay.opacity * 100)}%`; label.append(output);
    const slider = document.createElement("input"); slider.type = "range"; slider.id = label.htmlFor;
    slider.min = "0"; slider.max = "100"; slider.value = String(Math.round(overlay.opacity * 100));
    slider.addEventListener("input", () => {
        overlay.opacity = Number(slider.value) / 100; output.textContent = `${slider.value}%`;
        refreshManagedLayer(overlay);
    });
    const zoom = document.createElement("button"); zoom.type = "button"; zoom.className = "cad-action"; zoom.textContent = "Đến layer";
    zoom.addEventListener("click", () => fitManagedBounds(overlay.bounds));
    card.append(heading, meta, label, slider, zoom);
    const source = [...cadFiles, ...predictionFiles].find((entry) => entry.id === overlay.item.source_id);
    if (source) card.append(sourceRemoveButton(source, overlay.item.kind === "base" ? "cad" : "prediction"));
    $("layer-list").append(card);
}

function closeLayerInspector() {
    selectedLayerId = null; inspectorScope = "";
    $("layer-inspector").hidden = true;
    for (const card of document.querySelectorAll(".layer-card")) card.classList.remove("selected");
}

function selectManagedLayer(id, scope = "") {
    const overlay = overlays.find((entry) => entry.id === id);
    if (!overlay) return;
    const changed = selectedLayerId !== id;
    const opening = $("layer-inspector").hidden || changed;
    selectedLayerId = id;
    inspectorScope = overlay.groups.has(scope) ? scope : "";
    $("layer-inspector").hidden = false;
    $("inspector-title").textContent = overlay.item.name;
    const counts = new Map();
    for (const record of overlay.records) counts.set(record.feature.geometry.type, (counts.get(record.feature.geometry.type) || 0) + 1);
    $("inspector-meta").textContent = `${overlay.item.crs} · ${overlay.records.length.toLocaleString("vi-VN")} đối tượng. `
        + [...counts].map(([type, count]) => `${type}: ${count}`).join(" · ");
    $("inspector-warnings").textContent = Object.entries(overlay.item.data.warnings || {}).map(([reason, count]) => `${reason}: ${count}`).join("; ");
    const scopes = $("style-scope"); scopes.replaceChildren(new Option("Toàn bộ layer", ""));
    for (const group of overlay.groups.values()) scopes.append(new Option(`${group.name} (${group.count})`, group.name));
    scopes.value = inspectorScope;
    if (changed) { $("component-search").value = ""; $("attribute-search").value = ""; }
    componentPage = 0; attributePage = 0;
    $("feature-details").replaceChildren();
    for (const card of document.querySelectorAll(".layer-card")) card.classList.toggle("selected", card.dataset.layerId === id);
    renderStyleEditor(overlay); renderComponents(overlay); renderAttributes(overlay);
    renderColorAdjustments(overlay);
    if (opening) fitManagedBounds(overlay.bounds);
}

function currentOverlay() { return overlays.find((overlay) => overlay.id === selectedLayerId); }
function activeStyle(overlay) { return inspectorScope ? overlay.groups.get(inspectorScope).style : overlay.style; }

function renderStyleEditor(overlay) {
    const style = activeStyle(overlay);
    const first = overlay.records.find((record) => !inspectorScope || record.group === inspectorScope);
    const effective = first ? managedStyle(overlay, first.feature, false) : { color: overlay.color, fillColor: overlay.color, weight: 2, radius: 5, fillOpacity: 0.28 };
    $("style-source").checked = style.color == null && style.fillColor == null;
    $("style-stroke").value = effective.color;
    $("style-fill").value = effective.fillColor;
    for (const [id, value, suffix] of [
        ["style-weight", effective.weight, " px"], ["style-radius", effective.radius, " px"],
        ["style-fill-opacity", Math.round((style.fillOpacity ?? overlay.style.fillOpacity ?? first?.feature.properties?.fillOpacity ?? 0.28) * 100), "%"],
    ]) {
        $(id).value = value; $(`${id}-value`).textContent = `${value}${suffix}`;
    }
    $("style-dash").value = style.dashArray ?? overlay.style.dashArray ?? "";
}

function changeStyle(values) {
    const overlay = currentOverlay(); if (!overlay) return;
    Object.assign(activeStyle(overlay), values);
    refreshManagedLayer(overlay); renderStyleEditor(overlay);
    renderComponents(overlay);
}

function pager(container, page, total, onPage) {
    container.replaceChildren();
    const pages = Math.max(1, Math.ceil(total / 50));
    const previous = document.createElement("button"); previous.type = "button"; previous.textContent = "Trước"; previous.disabled = page <= 0;
    const next = document.createElement("button"); next.type = "button"; next.textContent = "Sau"; next.disabled = page + 1 >= pages;
    previous.addEventListener("click", () => onPage(page - 1)); next.addEventListener("click", () => onPage(page + 1));
    const label = document.createElement("span"); label.textContent = `${page + 1}/${pages} · ${total.toLocaleString("vi-VN")} mục`;
    container.append(previous, label, next);
}

function renderComponents(overlay) {
    const query = $("component-search").value.toLocaleLowerCase("vi-VN");
    const groups = [...overlay.groups.values()].filter((group) => group.name.toLocaleLowerCase("vi-VN").includes(query));
    componentPage = Math.min(componentPage, Math.max(0, Math.ceil(groups.length / 50) - 1));
    const list = $("component-list"); list.replaceChildren();
    for (const group of groups.slice(componentPage * 50, (componentPage + 1) * 50)) {
        const row = document.createElement("div"); row.className = "component-row";
        const toggle = document.createElement("input"); toggle.type = "checkbox"; toggle.checked = group.visible;
        toggle.setAttribute("aria-label", `Hiển thị thành phần ${group.name}`);
        toggle.addEventListener("change", () => { group.visible = toggle.checked; refreshManagedLayer(overlay); });
        const name = document.createElement("button"); name.type = "button"; name.textContent = `${group.name} (${group.count})`;
        name.addEventListener("click", () => {
            inspectorScope = group.name; $("style-scope").value = group.name;
            attributePage = 0; renderStyleEditor(overlay); renderAttributes(overlay);
        });
        const color = document.createElement("input"); color.type = "color";
        color.setAttribute("aria-label", `Màu thành phần ${group.name}`);
        const first = overlay.records.find((record) => record.group === group.name);
        color.value = managedStyle(overlay, first.feature, false).color;
        color.addEventListener("input", () => {
            group.style.color = color.value; group.style.fillColor = color.value;
            refreshManagedLayer(overlay); renderStyleEditor(overlay);
        });
        row.append(toggle, name, color); list.append(row);
    }
    pager($("component-pager"), componentPage, groups.length, (page) => { componentPage = page; renderComponents(overlay); });
}

function attributeText(value) { return value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value); }

function inspectFeature(overlay, record) {
    const details = $("feature-details"); details.replaceChildren();
    const heading = document.createElement("h3"); heading.textContent = `Đối tượng #${record.index + 1} · ${record.feature.geometry.type}`;
    const list = document.createElement("dl");
    for (const [key, value] of Object.entries(record.feature.properties || {})) {
        const term = document.createElement("dt"); term.textContent = key;
        const text = document.createElement("dd"); text.textContent = attributeText(value);
        list.append(term, text);
    }
    details.append(heading, list);
}

function renderAttributes(overlay) {
    const query = $("attribute-search").value.toLocaleLowerCase("vi-VN");
    const records = overlay.records.filter((record) => (!inspectorScope || record.group === inspectorScope)
        && (!query || Object.values(record.feature.properties || {}).some((value) => attributeText(value).toLocaleLowerCase("vi-VN").includes(query))));
    attributePage = Math.min(attributePage, Math.max(0, Math.ceil(records.length / 50) - 1));
    const columns = [...new Set(records.flatMap((record) => Object.keys(record.feature.properties || {})))];
    const table = $("attribute-table"); table.replaceChildren();
    const head = table.createTHead().insertRow();
    for (const name of ["#", "Hình học", ...columns]) { const th = document.createElement("th"); th.scope = "col"; th.textContent = name; head.append(th); }
    const body = table.createTBody();
    for (const record of records.slice(attributePage * 50, (attributePage + 1) * 50)) {
        const row = body.insertRow();
        const cell = row.insertCell(); const button = document.createElement("button"); button.type = "button"; button.textContent = String(record.index + 1);
        button.setAttribute("aria-label", `Xem đối tượng ${record.index + 1}`);
        button.addEventListener("click", () => {
            inspectFeature(overlay, record);
            const bounds = record.layer.getBounds ? record.layer.getBounds() : L.latLngBounds([record.layer.getLatLng(), record.layer.getLatLng()]);
            fitManagedBounds(bounds);
        }); cell.append(button);
        for (const value of [record.feature.geometry.type, ...columns.map((name) => record.feature.properties?.[name])]) {
            const td = row.insertCell(); td.textContent = attributeText(value); td.title = attributeText(value);
        }
    }
    pager($("attribute-pager"), attributePage, records.length, (page) => { attributePage = page; renderAttributes(overlay); });
}

$("inspector-close").addEventListener("click", closeLayerInspector);
$("fit-all-layers").addEventListener("click", fitAllManagedLayers);
$("style-scope").addEventListener("change", () => {
    inspectorScope = $("style-scope").value; attributePage = 0;
    const overlay = currentOverlay(); if (overlay) { renderStyleEditor(overlay); renderAttributes(overlay); }
});
$("style-stroke").addEventListener("input", () => changeStyle({ color: $("style-stroke").value }));
$("style-fill").addEventListener("input", () => changeStyle({ fillColor: $("style-fill").value }));
$("style-source").addEventListener("change", () => {
    const overlay = currentOverlay(); if (!overlay) return;
    const style = activeStyle(overlay);
    if ($("style-source").checked) { delete style.color; delete style.fillColor; }
    else { style.color = $("style-stroke").value; style.fillColor = $("style-fill").value; }
    refreshManagedLayer(overlay); renderStyleEditor(overlay); renderComponents(overlay);
});
for (const [id, key, divisor] of [["style-weight", "weight", 1], ["style-radius", "radius", 1], ["style-fill-opacity", "fillOpacity", 100]]) {
    $(id).addEventListener("input", () => changeStyle({ [key]: Number($(id).value) / divisor }));
}
$("style-dash").addEventListener("change", () => changeStyle({ dashArray: $("style-dash").value }));
$("style-reset").addEventListener("click", () => {
    const overlay = currentOverlay(); if (!overlay) return;
    if (inspectorScope) {
        overlay.groups.get(inspectorScope).style = {};
    } else {
        overlay.style = { weight: overlay.item.kind === "prediction" ? 1 : 2, radius: 5, dashArray: "" };
        for (const group of overlay.groups.values()) group.style = {};
        overlay.adjustments = { ...ColorAdjustments.defaults }; overlay.colorCache.clear();
    }
    refreshManagedLayer(overlay); renderStyleEditor(overlay); renderComponents(overlay);
    renderColorAdjustments(overlay);
});
$("component-search").addEventListener("input", () => { componentPage = 0; const overlay = currentOverlay(); if (overlay) renderComponents(overlay); });
$("attribute-search").addEventListener("input", () => { attributePage = 0; const overlay = currentOverlay(); if (overlay) renderAttributes(overlay); });
for (const color of layerPalette) {
    const button = document.createElement("button"); button.type = "button"; button.className = "palette-swatch";
    button.style.backgroundColor = color; button.setAttribute("aria-label", `Chọn màu ${color}`);
    button.addEventListener("click", () => { changeStyle({ color, fillColor: color }); const overlay = currentOverlay(); if (overlay) renderComponents(overlay); });
    $("style-palette").append(button);
}

function renderColorAdjustments(overlay) {
    for (const key of Object.keys(ColorAdjustments.defaults)) {
        $(`adjust-${key}`).value = overlay.adjustments[key];
        $(`adjust-${key}-value`).textContent = `${overlay.adjustments[key]}${key === "hue" ? "°" : "%"}`;
    }
}

function updateColorAdjustments(overlay, settings) {
    overlay.adjustments = ColorAdjustments.normalize(settings);
    overlay.colorCache.clear();
    refreshManagedLayer(overlay);
    renderColorAdjustments(overlay);
}

for (const key of Object.keys(ColorAdjustments.defaults)) {
    $(`adjust-${key}`).addEventListener("input", () => {
        const overlay = currentOverlay(); if (!overlay) return;
        updateColorAdjustments(overlay, { ...overlay.adjustments, [key]: Number($(`adjust-${key}`).value) });
    });
}
$("adjust-reset").addEventListener("click", () => {
    const overlay = currentOverlay(); if (overlay) updateColorAdjustments(overlay, ColorAdjustments.defaults);
});
