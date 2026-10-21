const $ = (id) => document.getElementById(id);
let predictionRows = [];
let predictionTableVersion = 0;
let map = null;
let referenceLabels = null;
let cadPreview = null;
let cadAnalysisCards = [];
let cadFiles = [];
let predictionFiles = [];
let overlays = [];
let pendingMapBounds = null;
let mapRequestVersion = 0;
let mapRequestController = null;
const sharedCrsStorageKey = "mapPredict.sharedCrs";
const labelsStorageKey = "mapPredict.labelsVisible";

function showStatus(id, message, error = false) {
    const element = $(id);
    element.textContent = message;
    element.className = `status-message ${error ? "text-danger" : "text-success"}`;
}

async function api(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Yêu cầu thất bại (${response.status}).`);
    return payload;
}

function fillSelect(select, values) {
    const previous = select.value;
    select.replaceChildren();
    for (const value of values) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.append(option);
    }
    if (values.includes(previous)) select.value = previous;
}

function crsDiagnosisText(diagnostics) {
    const bounds = diagnostics.raw_bounds;
    const range = bounds ? `X ${Math.round(bounds[0])}–${Math.round(bounds[2])}, Y ${Math.round(bounds[1])}–${Math.round(bounds[3])}. ` : "";
    return `${range}File ${diagnostics.declared_crs ? `khai báo ${diagnostics.declared_crs}` : "không khai báo EPSG"}. Khi hiển thị sẽ dùng hệ tọa độ chung bạn chọn ở thanh trên.`;
}

function offsetInput(name, value) {
    const input = document.createElement("input");
    input.type = "number";
    input.step = "any";
    input.name = name;
    input.value = String(value);
    return input;
}

function labeledControl(text, control) {
    const label = document.createElement("label");
    label.append(document.createTextNode(text), control);
    return label;
}

function updateCadOptions() {
    for (const state of cadAnalysisCards) {
        state.entry.offsetX = state.card.querySelector('[name="cad_offset_x"]').value;
        state.entry.offsetY = state.card.querySelector('[name="cad_offset_y"]').value;
    }
    resetCadAnalysis();
    cadAnalysisCards = [];
    const container = $("cad-options");
    container.replaceChildren();
    for (const entry of cadFiles) {
        const { file } = entry;
        const card = document.createElement("div");
        card.className = "cad-option";
        const title = document.createElement("strong");
        title.textContent = file.name;
        card.append(title);
        const offsets = document.createElement("div");
        offsets.className = "offset-fields";
        const offsetX = offsetInput("cad_offset_x", entry.offsetX || 0);
        const offsetY = offsetInput("cad_offset_y", entry.offsetY || 0);
        offsets.append(labeledControl("Dịch X (m)", offsetX), labeledControl("Dịch Y (m)", offsetY));
        card.append(offsets);
        const analyze = document.createElement("button");
        analyze.type = "button";
        analyze.className = "cad-action";
        analyze.textContent = "Phân tích độ dịch";
        const result = document.createElement("div");
        result.className = "cad-analysis";
        result.setAttribute("role", "status");
        result.setAttribute("aria-live", "polite");
        const state = { card, entry, analyze, result, version: 0, controller: null };
        cadAnalysisCards.push(state);
        analyze.addEventListener("click", () => analyzeCad(file, offsetX, offsetY, state));
        offsetX.addEventListener("input", clearCadPreview);
        offsetY.addEventListener("input", clearCadPreview);
        const remove = sourceRemoveButton(entry, "cad");
        card.append(analyze, remove, result);
        container.append(card);
    }
}

function appendSourceFiles(collection, files) {
    for (const file of files) {
        const key = JSON.stringify([file.name, file.size, file.lastModified]);
        if (!collection.some((entry) => entry.key === key)) {
            collection.push({ file, key, id: crypto.randomUUID() });
        }
    }
}

function sourceRemoveButton(entry, kind) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "cad-action source-remove";
    button.textContent = "Gỡ file";
    button.addEventListener("click", () => {
        ++mapRequestVersion;
        mapRequestController?.abort();
        $("map-button").disabled = false;
        $("map-button").textContent = "Hiển thị trên bản đồ";
        if (kind === "cad") {
            cadFiles = cadFiles.filter((source) => source !== entry);
            updateCadOptions();
        } else {
            predictionFiles = predictionFiles.filter((source) => source !== entry);
            updatePredictionSources();
        }
        renderMap(overlays.filter((overlay) => overlay.item.source_id !== entry.id).map((overlay) => overlay.item));
    });
    return button;
}

function updatePredictionSources() {
    const list = $("prediction-sources");
    list.replaceChildren();
    for (const entry of predictionFiles) {
        const row = document.createElement("div");
        row.className = "prediction-source";
        const name = document.createElement("span");
        name.textContent = `${entry.file.name}${entry.error ? ` · ${entry.error}` : ""}`;
        row.append(name, sourceRemoveButton(entry, "prediction"));
        list.append(row);
    }
    const columns = predictionFiles.length && predictionFiles.every((entry) => entry.columns)
        ? predictionFiles[0].columns.filter((name) => predictionFiles.every((entry) => entry.columns.includes(name))) : [];
    fillSelect($("gpkg-join"), columns);
    $("prediction-crs-info").textContent = predictionFiles.length
        ? `${predictionFiles.length} file GPKG. Các file dùng chung cột ghép, CSV kết quả và độ dịch X/Y bên dưới.` : "";
    updateJoinVisibility();
}

function clearCadPreview() {
    if (map && cadPreview) map.removeLayer(cadPreview);
    cadPreview = null;
}

function resetCadAnalysis() {
    clearCadPreview();
    for (const state of cadAnalysisCards) {
        ++state.version;
        state.controller?.abort();
        state.result.replaceChildren();
        state.result.removeAttribute("aria-busy");
        state.analyze.disabled = false;
        state.analyze.textContent = "Phân tích độ dịch";
    }
}

async function analyzeCad(file, offsetX, offsetY, state) {
    const sourceCrs = sharedSourceCrs();
    const { card, analyze, result } = state;
    clearCadPreview();
    result.replaceChildren();
    if (!/^EPSG:\d{4,6}$/.test(sourceCrs)) {
        result.textContent = "Chọn hệ tọa độ chung ở thanh trên trước khi phân tích.";
        return;
    }
    const version = ++state.version;
    state.controller?.abort();
    state.controller = new AbortController();
    analyze.disabled = true;
    analyze.textContent = "Đang phân tích…";
    result.textContent = "Đang đối chiếu các block và phép chèn. Không sửa file gốc.";
    result.setAttribute("aria-busy", "true");
    const form = new FormData();
    form.append("cad", file);
    form.append("source_crs", sourceCrs);
    try {
        const payload = await api("/api/cad-diagnostics", {
            method: "POST", body: form, signal: state.controller.signal,
        });
        if (!card.isConnected || version !== state.version || sourceCrs !== sharedSourceCrs()) return;
        result.replaceChildren();
        const message = document.createElement("p");
        message.textContent = payload.message;
        result.append(message);
        const candidate = payload.candidate;
        if (!candidate || payload.status !== "suggested") return;
        const details = document.createElement("p");
        details.className = "cad-analysis-details";
        details.textContent = `${payload.source_crs} · ΔX ${candidate.offset_x.toFixed(6)} m · ΔY ${candidate.offset_y.toFixed(6)} m. `
            + `${candidate.support_points} đỉnh đối chiếu; sai lệch phép dịch ≤ ${candidate.max_residual_m.toFixed(6)} m. `
            + `Tâm dự kiến: ${candidate.latitude.toFixed(6)}° Bắc, ${candidate.longitude.toFixed(6)}° Đông.`;
        const evidence = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = "Block làm căn cứ";
        const blockNames = document.createElement("p");
        blockNames.textContent = candidate.blocks.join("; ");
        evidence.append(summary, blockNames);
        const actions = document.createElement("div");
        actions.className = "cad-analysis-actions";
        const preview = document.createElement("button");
        preview.type = "button";
        preview.className = "cad-action";
        preview.textContent = "Xem trước vị trí";
        preview.addEventListener("click", () => {
            clearCadPreview();
            initializeMap();
            if (!map) return;
            const [west, south, east, north] = candidate.preview_bounds;
            const bounds = L.latLngBounds([[south, west], [north, east]]);
            const marker = L.circleMarker([candidate.latitude, candidate.longitude], {
                radius: 6, color: "#b45309", fillOpacity: 1,
            });
            const caption = document.createElement("span");
            caption.textContent = `Khung phạm vi đề xuất: ${file.name}. Chưa áp dụng độ dịch.`;
            marker.bindPopup(caption);
            cadPreview = L.layerGroup([
                L.rectangle(bounds, { color: "#b45309", weight: 2, dashArray: "7 5", fillOpacity: 0.08, interactive: false }),
                marker,
            ]).addTo(map);
            map.fitBounds(bounds, { padding: [32, 32], maxZoom: 17 });
            marker.openPopup();
            apply.disabled = false;
        });
        const apply = document.createElement("button");
        apply.type = "button";
        apply.className = "cad-action cad-action-apply";
        apply.textContent = "Áp dụng độ dịch";
        apply.disabled = true;
        apply.title = "Xem trước vị trí để mở bước xác nhận áp dụng.";
        apply.addEventListener("click", () => {
            // This replaces absolute offsets, never adds the proposal twice.
            offsetX.value = candidate.offset_x.toFixed(6);
            offsetY.value = candidate.offset_y.toFixed(6);
            clearCadPreview();
            applied.textContent = "Đã điền X/Y riêng cho file này. Nhấn Hiển thị trên bản đồ để nạp lại layer. EPSG chung không thay đổi.";
        });
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "cad-action";
        cancel.textContent = "Đóng đề xuất";
        cancel.addEventListener("click", () => { clearCadPreview(); result.replaceChildren(); });
        const applied = document.createElement("p");
        actions.append(preview, apply, cancel);
        result.append(details, evidence, actions, applied);
    } catch (error) {
        if (version === state.version && card.isConnected && error.name !== "AbortError") {
            result.textContent = `Không thể phân tích: ${error.message}`;
        }
    } finally {
        if (version === state.version) {
            analyze.disabled = false;
            analyze.textContent = "Phân tích lại độ dịch";
            result.removeAttribute("aria-busy");
        }
    }
}

function sharedSourceCrs() {
    return ($("project-crs").value === "custom"
        ? $("project-crs-custom").value.trim() : $("project-crs").value).toUpperCase();
}

function applySharedCrs(reload = false) {
    const custom = $("project-crs").value === "custom";
    $("project-crs-custom").hidden = !custom;
    $("project-crs-custom").disabled = !custom;
    $("project-crs-custom").required = custom;
    const crs = sharedSourceCrs();
    if ($("source-crs").value !== crs) resetCadAnalysis();
    $("source-crs").value = crs;
    try {
        if (/^EPSG:\d{4,6}$/.test(crs)) localStorage.setItem(sharedCrsStorageKey, crs);
        else localStorage.removeItem(sharedCrsStorageKey);
    } catch { /* Browser storage is optional. */ }
    if (reload && overlays.length && /^EPSG:\d{4,6}$/.test(crs)) {
        $("map-form").requestSubmit();
    } else if (!overlays.length) {
        $("map-crs-status").textContent = crs ? `Hệ chung: ${crs}` : "Chưa chọn hệ tọa độ chung";
    }
}

try {
    const savedCrs = localStorage.getItem(sharedCrsStorageKey);
    if (savedCrs && /^EPSG:\d{4,6}$/.test(savedCrs)) {
        const listed = [...$("project-crs").options].some((option) => option.value === savedCrs);
        $("project-crs").value = listed ? savedCrs : "custom";
        if (!listed) $("project-crs-custom").value = savedCrs;
    }
} catch { /* Continue with an unselected CRS if storage is unavailable. */ }
applySharedCrs();
$("project-crs").addEventListener("change", () => applySharedCrs(true));
$("project-crs-custom").addEventListener("change", () => applySharedCrs(true));

function renderPredictionTable(rows, isResult, total = rows.length) {
    const hasData = rows.length > 0;
    $("prediction-empty").hidden = hasData;
    $("prediction-table-scroll").hidden = !hasData;
    $("prediction-export").hidden = !hasData || !isResult;
    $("prediction-title").textContent = hasData
        ? (isResult ? "Kết quả dự đoán" : "Dữ liệu đầu vào") : "Bảng dữ liệu";
    const table = $("prediction-table");
    table.replaceChildren();
    if (!hasData) {
        $("prediction-count").textContent = "Chưa có dữ liệu để hiển thị.";
        return;
    }

    const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
    const header = document.createElement("thead");
    const headerRow = document.createElement("tr");
    const numberHeader = document.createElement("th");
    numberHeader.textContent = "#";
    numberHeader.className = "row-number";
    numberHeader.scope = "col";
    headerRow.append(numberHeader);
    for (const column of columns) {
        const cell = document.createElement("th");
        cell.scope = "col";
        cell.textContent = column;
        if (isResult && column === "Y") cell.className = "prediction-output";
        headerRow.append(cell);
    }
    header.append(headerRow);
    table.append(header);

    const body = document.createElement("tbody");
    for (const [index, row] of rows.slice(0, 200).entries()) {
        const tr = document.createElement("tr");
        const rowNumber = document.createElement("th");
        rowNumber.className = "row-number";
        rowNumber.scope = "row";
        rowNumber.textContent = String(index + 1);
        tr.append(rowNumber);
        for (const column of columns) {
            const cell = document.createElement("td");
            cell.textContent = row[column] ?? "";
            cell.title = String(row[column] ?? "");
            if (isResult && column === "Y") cell.className = "prediction-output";
            tr.append(cell);
        }
        body.append(tr);
    }
    table.append(body);
    $("prediction-count").textContent = total > 200
        ? `Hiển thị 200/${total.toLocaleString("vi-VN")} dòng · ${columns.length} cột${isResult ? ". Xuất CSV để tải toàn bộ kết quả." : "."}`
        : `${total.toLocaleString("vi-VN")} dòng · ${columns.length} cột`;
    $("prediction-table-scroll").scrollTo(0, 0);
}

function renderResults(rows, display = true) {
    predictionRows = rows;
    if (display) renderPredictionTable(rows, true);
    const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
    fillSelect($("csv-join"), columns.filter((name) => name !== "Y"));
    updateJoinVisibility();
}

function updateJoinVisibility() {
    $("join-controls").hidden = !predictionFiles.length;
}

function initializeMap() {
    if (map) {
        map.invalidateSize();
        if (!$("map-panel").hidden && pendingMapBounds) {
            map.fitBounds(pendingMapBounds, { padding: [24, 24], maxZoom: 17 });
            pendingMapBounds = null;
        }
        return;
    }
    if (!window.L) {
        showStatus("map-message", "Không tải được Leaflet. Kiểm tra kết nối mạng.", true);
        return;
    }
    map = L.map("leafletMap", {
        zoomControl: true,
        zoomAnimation: false,
        fadeAnimation: false,
        markerZoomAnimation: false,
    }).setView([16.2, 107.5], 6);
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 19,
        attribution: 'Imagery &copy; <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics, and the GIS User Community',
    }).addTo(map);
    // Keep basemap names above user geometry without intercepting feature clicks.
    const labelsPane = map.createPane("referenceLabels");
    labelsPane.style.zIndex = "625";
    labelsPane.style.pointerEvents = "none";
    referenceLabels = L.layerGroup([
        "World_Transportation", "World_Boundaries_and_Places",
    ].map((service) => L.tileLayer(
        `https://services.arcgisonline.com/ArcGIS/rest/services/Reference/${service}/MapServer/tile/{z}/{y}/{x}`,
        {
            pane: "referenceLabels",
            maxZoom: 19,
            attribution: 'Labels &copy; <a href="https://www.esri.com/">Esri</a>, HERE, Garmin',
        },
    )));
    try {
        $("basemap-labels").checked = localStorage.getItem(labelsStorageKey) !== "false";
    } catch { /* Keep labels enabled when browser storage is unavailable. */ }
    if ($("basemap-labels").checked) referenceLabels.addTo(map);
}

$("basemap-labels").addEventListener("change", (event) => {
    const visible = event.target.checked;
    if (map && referenceLabels) {
        if (visible) referenceLabels.addTo(map);
        else map.removeLayer(referenceLabels);
    }
    try {
        localStorage.setItem(labelsStorageKey, String(visible));
    } catch { /* Toggling labels does not require browser storage. */ }
});

function renderMap(layers) {
    clearCadPreview();
    initializeMap();
    if (!map) return;
    const previous = overlays;
    for (const overlay of previous) map.removeLayer(overlay.layer);
    overlays = [];
    const list = $("layer-list");
    list.replaceChildren();
    const bounds = L.latLngBounds();
    const colors = ["#0b8753", "#d97706", "#2563eb", "#9333ea", "#e11d48"];
    for (const [index, item] of layers.entries()) {
        const saved = previous[index]?.item.name === item.name
            && previous[index]?.item.kind === item.kind ? previous[index] : null;
        const opacity = saved?.opacity ?? 1;
        const isPrediction = item.kind === "prediction";
        const color = colors[index % colors.length];
        const style = (feature, opacity) => ({
            color: isPrediction ? "#334155" : color,
            weight: isPrediction ? 1 : 2,
            opacity,
            fillColor: isPrediction ? (feature.properties?.fillColor || "#cccccc") : color,
            fillOpacity: (isPrediction ? (feature.properties?.fillOpacity ?? 0) : 0.28) * opacity,
        });
        const layer = L.geoJSON(item.data, {
            style: (feature) => style(feature, opacity),
            pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
                radius: 5,
                ...style(feature, opacity),
            }),
            onEachFeature: (feature, featureLayer) => {
                if (!isPrediction || !feature.properties) return;
                const properties = feature.properties;
                const joinKey = Object.keys(properties).find((key) => !["Y", "fillColor", "fillOpacity"].includes(key));
                if (!joinKey) return;
                const popup = document.createElement("div");
                const name = document.createElement("strong");
                name.textContent = `${joinKey}: `;
                popup.append(name, document.createTextNode(String(properties[joinKey] ?? "")));
                popup.append(document.createElement("br"));
                popup.append(document.createTextNode(`Kết quả dự đoán (Y): ${properties.Y ?? "Chưa có"}`));
                featureLayer.bindPopup(popup);
            },
        });
        const overlay = { layer, item, visible: saved?.visible ?? true, opacity };
        if (overlay.visible) layer.addTo(map);
        overlays.push(overlay);
        if (layer.getLayers().length) bounds.extend(layer.getBounds());

        const card = document.createElement("div");
        card.className = "layer-card";
        const heading = document.createElement("div");
        heading.className = "layer-card-heading";
        const toggle = document.createElement("input");
        toggle.type = "checkbox";
        toggle.checked = overlay.visible;
        toggle.id = `layer-visible-${index}`;
        toggle.setAttribute("aria-label", `Hiển thị ${item.name || `Layer ${index + 1}`}`);
        toggle.addEventListener("change", () => {
            overlay.visible = toggle.checked;
            if (toggle.checked) layer.addTo(map);
            else map.removeLayer(layer);
        });
        const name = document.createElement("label");
        name.htmlFor = toggle.id;
        name.textContent = item.name || `Layer ${index + 1}`;
        heading.append(toggle, name);
        const meta = document.createElement("p");
        meta.className = "layer-meta";
        const offset = item.offset_x || item.offset_y
            ? ` · ΔX ${item.offset_x || 0} m, ΔY ${item.offset_y || 0} m` : "";
        meta.textContent = `${item.crs || "EPSG không rõ"} · ${item.data.features.length.toLocaleString("vi-VN")} đối tượng${offset}`;
        const sliderLabel = document.createElement("label");
        sliderLabel.className = "opacity-label";
        sliderLabel.htmlFor = `layer-opacity-${index}`;
        sliderLabel.textContent = "Độ đậm";
        const value = document.createElement("output");
        value.textContent = `${Math.round(opacity * 100)}%`;
        sliderLabel.append(value);
        const slider = document.createElement("input");
        slider.type = "range";
        slider.id = sliderLabel.htmlFor;
        slider.min = "0";
        slider.max = "100";
        slider.value = String(Math.round(opacity * 100));
        slider.addEventListener("input", () => {
            const opacity = Number(slider.value) / 100;
            overlay.opacity = opacity;
            value.textContent = `${slider.value}%`;
            layer.setStyle((feature) => style(feature, opacity));
        });
        card.append(heading, meta, sliderLabel, slider);
        list.append(card);
    }
    $("layer-count").textContent = String(layers.length);
    if (bounds.isValid()) {
        if ($("map-panel").hidden) pendingMapBounds = bounds;
        else map.fitBounds(bounds, { padding: [24, 24], maxZoom: 17 });
    }
}

for (const input of document.querySelectorAll('input[type="file"]')) {
    input.addEventListener("change", () => {
        const label = document.querySelector(`[data-file-label="${input.id}"]`);
        if (label) label.textContent = input.files[0]?.name || label.dataset.defaultLabel || "Chưa chọn file";
        if (input.id === "layer-file") updateJoinVisibility();
        if (input.id === "cad-file") updateCadOptions();
    });
}

for (const [tabId, panelId, otherTabId, otherPanelId] of [
    ["predict-tab", "predict-panel", "map-tab", "map-panel"],
    ["map-tab", "map-panel", "predict-tab", "predict-panel"],
]) {
    $(tabId).addEventListener("click", () => {
        $(panelId).hidden = false;
        $(otherPanelId).hidden = true;
        $(tabId).classList.add("active");
        $(otherTabId).classList.remove("active");
        $(tabId).setAttribute("aria-selected", "true");
        $(otherTabId).setAttribute("aria-selected", "false");
        if (panelId === "map-panel") setTimeout(initializeMap, 0);
        document.body.classList.toggle("map-mode", panelId === "map-panel");
    });
}

$("csv-file").addEventListener("change", async (event) => {
    const version = ++predictionTableVersion;
    const file = event.target.files[0];
    if (!file) {
        renderResults(predictionRows);
        showStatus("predict-message", "");
        return;
    }
    const form = new FormData();
    form.append("csv", file);
    showStatus("predict-message", "Đang đọc dữ liệu CSV...");
    try {
        const payload = await api("/api/preview-csv", { method: "POST", body: form });
        if (version !== predictionTableVersion) return;
        renderPredictionTable(payload.rows, false, payload.count);
        showStatus("predict-message", `Đã nạp ${payload.count.toLocaleString("vi-VN")} dòng. Sẵn sàng dự đoán.`);
    } catch (error) {
        if (version !== predictionTableVersion) return;
        renderPredictionTable([], false);
        showStatus("predict-message", `Lỗi: ${error.message}`, true);
    }
});

$("predict-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    ++predictionTableVersion;
    const form = new FormData(event.currentTarget);
    const inputs = [...event.currentTarget.querySelectorAll('input[type="file"]')];
    inputs.forEach((input) => { input.disabled = true; });
    const button = $("predict-button");
    button.disabled = true;
    button.textContent = "Đang xử lý...";
    $("prediction-result").setAttribute("aria-busy", "true");
    showStatus("predict-message", "");
    try {
        const payload = await api("/api/predict", {
            method: "POST", body: form,
        });
        renderResults(payload.rows);
        showStatus("predict-message", `Đã dự đoán ${payload.rows.length.toLocaleString("vi-VN")} dòng. Có thể xuất CSV ở bảng bên phải.`);
    } catch (error) {
        showStatus("predict-message", `Lỗi: ${error.message}`, true);
    } finally {
        button.disabled = false;
        button.textContent = "Bắt đầu dự đoán";
        inputs.forEach((input) => { input.disabled = false; });
        $("prediction-result").removeAttribute("aria-busy");
    }
});

$("layer-file").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("gpkg", file);
    try {
        const payload = await api("/api/gpkg-columns", { method: "POST", body: form });
        fillSelect($("gpkg-join"), payload.columns);