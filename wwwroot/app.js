const $ = (id) => document.getElementById(id);
let predictionRows = [];
let predictionTableVersion = 0;
let predictionView = null;
let predictionDownloadUrl = null;
let map = null;
let referenceLabels = null;
let basemapLayers = null;
let activeBasemap = null;
let cadPreview = null;
let cadAnalysisCards = [];
let cadFiles = [];
let predictionFiles = [];
let gpkgJoinPreference = "";
let overlays = [];
let pendingMapBounds = null;
let mapRequestVersion = 0;
let mapRequestController = null;
let resultColumnsLoading = false;
let resultColumnsVersion = 0;
const joinPreview = window.JoinPreview.create({
    container: $("join-preview"), button: $("join-apply"), apply: applyMapPayload,
});
const sharedCrsStorageKey = "mapPredict.sharedCrs";
const labelsStorageKey = "mapPredict.labelsVisible";
const basemapStorageKey = "mapPredict.basemap";

function showStatus(id, message, error = false) {
    const element = $(id);
    element.textContent = message;
    element.className = `status-message ${error ? "text-danger" : "text-success"}`;
    window.workspacePersistence?.schedule();
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
    invalidateMapPreview();
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
    window.workspacePersistence?.schedule();
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

function commonPredictionColumns() {
    return predictionFiles.length && predictionFiles.every((entry) => entry.columns)
        ? predictionFiles[0].columns.filter((name) => predictionFiles.every((entry) => entry.columns.includes(name))) : [];
}

function individualPredictionJoins() {
    return new Set(predictionFiles.map((entry) => entry.file.name.split(".").pop().toLowerCase())).size > 1
        || (predictionFiles.length > 0 && predictionFiles.every((entry) => entry.columns) && !commonPredictionColumns().length);
}

function updatePredictionSources() {
    invalidateMapPreview();
    gpkgJoinPreference = $("gpkg-join").value || gpkgJoinPreference;
    const list = $("prediction-sources");
    list.replaceChildren();
    for (const entry of predictionFiles) {
        const row = document.createElement("div");
        row.className = "prediction-source";
        const name = document.createElement("span");
        name.textContent = `${entry.file.name}${entry.error ? ` · ${entry.error}` : ""}`;
        row.append(name, sourceRemoveButton(entry, "prediction"));
        if (entry.diagnostics?.format === "dxf") {
            const note = document.createElement("p");
            note.className = "field-note";
            note.textContent = `${entry.diagnostics.cell_count} ô kín; ${entry.diagnostics.identified_count} ô có mã duy nhất. `
                + "grid_id đọc từ nhãn TEXT/MTEXT trong ô, không phải thuộc tính tenlodat gốc. "
                + "Không ghép theo thứ tự ô hay cao độ POINT.";
            row.append(note);
            for (const [warning, count] of Object.entries(entry.diagnostics.warnings || {})) {
                const message = document.createElement("p"); message.className = "field-note text-danger";
                message.textContent = `${warning}: ${count}`; row.append(message);
            }
        }
        if (individualPredictionJoins() && entry.columns) {
            const select = document.createElement("select");
            select.className = "prediction-source-join";
            select.setAttribute("aria-label", `Cột ghép ${entry.file.name}`);
            fillSelect(select, entry.columns);
            const preferred = entry.joinColumn || entry.suggestedJoin || gpkgJoinPreference;
            if (entry.columns.includes(preferred)) select.value = preferred;
            entry.joinColumn = select.value;
            select.addEventListener("change", () => { entry.joinColumn = select.value; });
            row.append(labeledControl("Cột ghép trong file", select));
        }
        list.append(row);
    }
    const columns = commonPredictionColumns();
    fillSelect($("gpkg-join"), columns);
    if (columns.includes(gpkgJoinPreference)) $("gpkg-join").value = gpkgJoinPreference;
    else if (columns.includes("grid_id")) $("gpkg-join").value = "grid_id";
    $("common-layer-join").hidden = individualPredictionJoins();
    $("gpkg-join").disabled = individualPredictionJoins();
    $("prediction-crs-info").textContent = predictionFiles.length
        ? `${predictionFiles.length} file lưới DXF/GPKG. ${individualPredictionJoins() ? "Chọn cột ghép riêng ở từng file." : "Các file dùng chung cột ghép."} Dùng chung hệ tọa độ nguồn, CSV và độ dịch X/Y. DXF chưa có kết quả vẫn xem được đường ô.` : "";
    updateJoinVisibility();
    window.workspacePersistence?.schedule();
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
            invalidateMapPreview();
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

function resultsCsvFile(rows) {
    const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
    const quote = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
    const lines = [columns.map(quote).join(","), ...rows.map((row) => columns.map((key) => quote(row[key])).join(","))];
    return new File(["\ufeff", lines.join("\r\n")], "KetQua.csv", { type: "text/csv;charset=utf-8" });
}

function renderPredictionTable(rows, isResult, total = rows.length) {
    predictionView = { rows, isResult, total };
    window.workspacePersistence?.schedule();
    const hasData = rows.length > 0;
    $("prediction-empty").hidden = hasData;
    $("prediction-table-scroll").hidden = !hasData;
    $("prediction-export").hidden = !hasData || !isResult;
    if (predictionDownloadUrl) URL.revokeObjectURL(predictionDownloadUrl);
    predictionDownloadUrl = hasData && isResult ? URL.createObjectURL(resultsCsvFile(rows)) : null;
    $("prediction-export").href = predictionDownloadUrl || "#";
    $("prediction-export").download = "KetQua.csv";
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
    invalidateMapPreview();
    predictionRows = rows;
    if (display) renderPredictionTable(rows, true);
    const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
    fillSelect($("csv-join"), columns.filter((name) => name !== "Y"));
    updateJoinVisibility();
}

function updateJoinVisibility() {
    $("join-controls").hidden = !predictionFiles.length;
    $("join-preview-button").hidden = !predictionFiles.length;
}

function updateBasemapLabels() {
    const satellite = activeBasemap === "satellite";
    $("basemap-labels").disabled = !satellite;
    $("basemap-labels-note").textContent = satellite
        ? "Nhãn đường và địa danh Esri. Không bật nhãn chữ trong DXF."
        : "Nền đường phố đã có nhãn riêng; công tắc nhãn chỉ áp dụng cho vệ tinh.";
    if (!map || !referenceLabels) return;
    if (satellite && $("basemap-labels").checked) referenceLabels.addTo(map);
    else map.removeLayer(referenceLabels);
}

function selectBasemap(value) {
    if (!map || !basemapLayers) return;
    const next = Object.hasOwn(basemapLayers, value) ? value : "satellite";
    if (activeBasemap !== next) {
        if (activeBasemap) map.removeLayer(basemapLayers[activeBasemap]);
        activeBasemap = next;
        basemapLayers[next].addTo(map);
    }
    $("basemap-select").value = next;
    $("map-basemap-status").textContent = next === "satellite" ? "Vệ tinh Esri" : "Đường phố OpenStreetMap";
    $("basemap-message").textContent = "";
    updateBasemapLabels();
    try { localStorage.setItem(basemapStorageKey, next); } catch { /* Optional preference. */ }
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
        ...Basemaps.motionOptions(),
        zoomControl: true,
        preferCanvas: true,
        renderer: L.canvas({ padding: 0.3 }),
        minZoom: 2,
        maxZoom: Basemaps.MAX_ZOOM,
    }).setView([16.2, 107.5], 6);
    basemapLayers = {
        // blankTile=false makes missing Esri coverage detectable (404), rather
        // than displaying the provider's grey "Map data not yet available" image.
        satellite: Basemaps.createFallbackLayer(L,
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?blankTile=false", {
                attribution: 'Imagery &copy; <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics, and the GIS User Community',
            }),
        streets: Basemaps.createFallbackLayer(L, "https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            nativeMaxZoom: 19, fallbackDepth: 0,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        }),
    };
    for (const [key, layer] of Object.entries(basemapLayers)) {
        const failedTiles = new Set();
        const tileKey = ({ coords }) => `${coords.z}:${coords.x}:${coords.y}`;
        layer.on("tileerror", (event) => {
            failedTiles.add(tileKey(event));
            if (activeBasemap === key) $("basemap-message").textContent = "Không tải được một phần nền bản đồ. Kiểm tra Internet hoặc đổi nền; layer của bạn vẫn được giữ.";
        });
        layer.on("tileload tileunload", (event) => failedTiles.delete(tileKey(event)));
        layer.on("load", () => {
            if (activeBasemap === key && !failedTiles.size) $("basemap-message").textContent = "";
        });
    }
    // Keep basemap names above user geometry without intercepting feature clicks.
    const labelsPane = map.createPane("referenceLabels");
    labelsPane.style.zIndex = "625";
    labelsPane.style.pointerEvents = "none";
    referenceLabels = L.layerGroup([
        "World_Transportation", "World_Boundaries_and_Places",
    ].map((service) => Basemaps.createFallbackLayer(L,
        `https://services.arcgisonline.com/ArcGIS/rest/services/Reference/${service}/MapServer/tile/{z}/{y}/{x}?blankTile=false`,
        {
            pane: "referenceLabels",
            nativeMaxZoom: 18,
            attribution: 'Labels &copy; <a href="https://www.esri.com/">Esri</a>, HERE, Garmin',
        },
    )));
    try {
        $("basemap-labels").checked = localStorage.getItem(labelsStorageKey) !== "false";
    } catch { /* Keep labels enabled when browser storage is unavailable. */ }
    let preferredBasemap = "satellite";
    try { preferredBasemap = localStorage.getItem(basemapStorageKey) || preferredBasemap; } catch { /* Default imagery. */ }
    selectBasemap(preferredBasemap);
}

$("basemap-select").addEventListener("change", (event) => selectBasemap(event.target.value));

$("basemap-labels").addEventListener("change", (event) => {
    const visible = event.target.checked;
    updateBasemapLabels();
    try {
        localStorage.setItem(labelsStorageKey, String(visible));
    } catch { /* Toggling labels does not require browser storage. */ }
});

function renderMap(layers, savedLayers = null) {
    clearCadPreview();
    initializeMap();
    if (!map) return;
    renderManagedLayers(layers, savedLayers);
    window.workspacePersistence?.schedule();
}

for (const input of document.querySelectorAll('input[type="file"]')) {
    input.addEventListener("change", () => {
        const label = document.querySelector(`[data-file-label="${input.id}"]`);
        if (label) label.textContent = input.files[0]?.name || label.dataset.defaultLabel || "Chưa chọn file";
        if (input.id === "cad-file") {
            appendSourceFiles(cadFiles, [...input.files]);
            input.value = "";
            updateCadOptions();
        }
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
    const version = ++predictionTableVersion;
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
        if (version !== predictionTableVersion) return;
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

async function readPredictionSources() {
    const pending = predictionFiles.filter((entry) => !entry.columns && !entry.loading);
    pending.forEach((entry) => { entry.loading = true; });
    updatePredictionSources();
    await Promise.all(pending.map(async (entry) => {
        const form = new FormData();
        form.append("layer", entry.file);
        try {
            const payload = await api("/api/prediction-columns", { method: "POST", body: form });
            entry.columns = payload.columns;
            entry.diagnostics = payload.diagnostics;
            entry.suggestedJoin = payload.suggested_join;
            entry.error = null;
        } catch (error) {
            entry.error = error.message;
        } finally {
            entry.loading = false;
            updatePredictionSources();
        }
    }));
}

$("layer-file").addEventListener("change", async (event) => {
    appendSourceFiles(predictionFiles, [...event.target.files]);
    event.target.value = "";
    await readPredictionSources();
});

$("result-file").addEventListener("change", async (event) => {
    const version = ++resultColumnsVersion;
    const file = event.target.files[0];
    resultColumnsLoading = !!file;
    if (!file) {
        fillSelect($("csv-join"), predictionRows.length
            ? Object.keys(predictionRows[0]).filter((name) => name !== "Y") : []);
        return;
    }
    const form = new FormData();
    form.append("result", file);
    try {
        const payload = await api("/api/result-columns", { method: "POST", body: form });
        if (version !== resultColumnsVersion) return;
        fillSelect($("csv-join"), payload.columns);
        showStatus("map-message", `Đã nạp file kết quả: ${file.name}`);
    } catch (error) {
        if (version !== resultColumnsVersion) return;
        fillSelect($("csv-join"), []);
        showStatus("map-message", `Lỗi: ${error.message}`, true);
    } finally {
        if (version === resultColumnsVersion) resultColumnsLoading = false;
    }
});

function invalidateMapPreview() {
    ++mapRequestVersion;
    mapRequestController?.abort();
    joinPreview.invalidate();
    $("map-button").disabled = false;
    $("map-button").textContent = "Hiển thị trên bản đồ";
}

function applyMapPayload(payload) {
    renderMap(payload.layers);
    $("map-crs-status").textContent = `Hệ chung: ${payload.source_crs}`;
    const summaries = payload.layers.filter((layer) => layer.data.join_summary).map((layer) => {
        const summary = layer.data.join_summary;
        return summary.results_applied
            ? `${layer.name}: ${summary.matched}/${summary.total} ô khớp, ${summary.unmatched} ô chưa tô màu`
            : `${layer.name}: ${summary.total} ô, chưa áp dụng kết quả dự đoán`;
    });
    showStatus("map-message", `Đã tải ${payload.layers.length} layer theo ${payload.source_crs} ${summaries.join(" · ")}`);
}

$("join-preview-button").addEventListener("click", () => $("map-form").requestSubmit());
for (const event of ["input", "change"]) {
    $("map-form").addEventListener(event, invalidateMapPreview);
    $("project-crs").addEventListener(event, invalidateMapPreview, true);
    $("project-crs-custom").addEventListener(event, invalidateMapPreview, true);
}

$("map-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const version = ++mapRequestVersion;
    mapRequestController?.abort();
    mapRequestController = new AbortController();
    $("source-crs").value = sharedSourceCrs();
    const button = $("map-button");
    button.disabled = true;
    button.textContent = "Đang tải bản đồ...";
    showStatus("map-message", "");
    try {
        joinPreview.invalidate();
        if (resultColumnsLoading) throw new Error("Chờ đọc xong file kết quả CSV trước khi ghép");
        const form = new FormData(event.currentTarget);
        if (predictionFiles.length && !$("result-file").files.length
            && predictionRows.length) {
            form.set("result", resultsCsvFile(predictionRows));
        }
        if (predictionFiles.some((entry) => entry.loading || !entry.columns)) {
            throw new Error("Chờ đọc xong lưới DXF/GPKG hoặc gỡ file đang báo lỗi trước khi hiển thị.");
        }
        form.delete("cad");
        form.delete("layer");
        for (const entry of cadFiles) {
            form.append("cad", entry.file);
            form.append("cad_id", entry.id);
        }
        for (const entry of predictionFiles) {
            form.append("layer", entry.file);
            form.append("layer_id", entry.id);
            form.append("layer_join", individualPredictionJoins() ? entry.joinColumn : $("gpkg-join").value);
        }
        const payload = await api("/api/map", {
            method: "POST", body: form, signal: mapRequestController.signal,
        });
        if (version !== mapRequestVersion) return;
        if (payload.layers.some((layer) => layer.data.join_summary?.results_applied)) {
            joinPreview.show(payload);
            showStatus("map-message", "Đã xem trước ghép kết quả, chọn Áp dụng kết quả lên bản đồ sau khi kiểm tra");
        } else applyMapPayload(payload);
    } catch (error) {
        if (version !== mapRequestVersion || error.name === "AbortError") return;
        showStatus("map-message", `Lỗi: ${error.message}`, true);
    } finally {
        if (version === mapRequestVersion) {
            button.disabled = false;
            button.textContent = "Hiển thị trên bản đồ";
        }
    }
});

initializeMap();

// Project resources are the assistant's inputs, not separate chat attachments.
window.assistantWorkspace = {
    sources() {
        return [...cadFiles.map(entry => ({ ...entry, kind: 'cad' })),
            ...predictionFiles.map(entry => ({ ...entry, kind: 'prediction' }))]
            .filter(entry => entry.file.name.toLowerCase().endsWith('.dxf'));
    },
    tables() { return ['csv-file', 'result-file'].flatMap(id =>
        $(id).files[0] ? [{ id, file: $(id).files[0] }] : []); },
    csv(id = 'csv-file') { return $(id)?.files[0] || null; },
    version() { return `${predictionTableVersion}:${mapRequestVersion}:${resultColumnsVersion}:${sharedSourceCrs()}`; },
    crs() { return sharedSourceCrs(); },
    async commit({ sourceId, original, dxf, rows, csvId = 'csv-file' }) {
        if (!window.workspacePersistence?.ready) throw new Error('Workspace chưa khôi phục xong, hãy chờ hoặc kiểm tra trạng thái bản lưu');
        const entry = [...cadFiles, ...predictionFiles].find(item => item.id === sourceId);
        if (sourceId && (!entry || entry.file !== original)) throw new Error('File DXF đã thay đổi, hãy tạo lại bản xem trước');
        if (rows) {
            const name = this.csv(csvId)?.name || 'TieuChi.csv';
            const file = new File([await resultsCsvFile(rows).arrayBuffer()], name, { type: 'text/csv;charset=utf-8' });
            const transfer = new DataTransfer();
            transfer.items.add(file);
            $('csv-file').files = transfer.files;
            // Scoring invalidates old predictions, including a separately imported result CSV.
            $('result-file').files = new DataTransfer().files;
            const resultLabel = document.querySelector('[data-file-label="result-file"]');
            if (resultLabel) resultLabel.textContent = 'Chưa chọn file';
            const label = document.querySelector('[data-file-label="csv-file"]');
            if (label) label.textContent = file.name;
            ++predictionTableVersion;
            renderResults([], false);
            renderPredictionTable(rows, false);
            showStatus('predict-message', 'Đã áp dụng tiêu chí từ chatbot, có thể kiểm tra bảng rồi chạy mô hình');
        }
        if (dxf) {
            if (entry) {
                entry.file = dxf;
                entry.key = JSON.stringify([dxf.name, dxf.size, dxf.lastModified]);
                delete entry.columns;
                delete entry.diagnostics;
                delete entry.error;
            } else appendSourceFiles(cadFiles, [dxf]);
            ++mapRequestVersion;
            mapRequestController?.abort();
            updateCadOptions();
            updatePredictionSources();
            await readPredictionSources();
        }
        if ((dxf || rows) && sharedSourceCrs() && (cadFiles.length || predictionFiles.length)) {
            const version = ++mapRequestVersion;
            mapRequestController?.abort();
            mapRequestController = new AbortController();
            $('source-crs').value = sharedSourceCrs();
            const form = new FormData($('map-form'));
            form.delete('cad'); form.delete('layer');
            for (const item of cadFiles) { form.append('cad', item.file); form.append('cad_id', item.id); }
            for (const item of predictionFiles) {
                if (item.error || !item.columns) throw new Error('Không đọc được lưới đã sửa');
                form.append('layer', item.file); form.append('layer_id', item.id);
                form.append('layer_join', individualPredictionJoins() ? item.joinColumn : $('gpkg-join').value);
            }
            if (predictionRows.length && !$('result-file').files.length) form.set('result', resultsCsvFile(predictionRows));
            const payload = await api('/api/map', { method: 'POST', body: form, signal: mapRequestController.signal });
            if (version !== mapRequestVersion) throw new Error('Bản đồ vừa thay đổi, hãy tạo lại đề xuất');
            const center = map?.getCenter(), zoom = map?.getZoom();
            const styles = overlays;
            renderMap(payload.layers, styles);
            if (center) { pendingMapBounds = null; map.setView(center, zoom, { animate: false }); }
        } else if (dxf && overlays.length) {
            throw new Error('Chọn hệ tọa độ để hiển thị DXF đã sửa trên bản đồ');
        }
        window.workspacePersistence?.schedule();
    },
};

const assistantHistory = new WorkspaceHistory({
    capture: () => window.workspacePersistence.checkpoint(),
    restore: snapshot => window.workspacePersistence.restoreCheckpoint(snapshot),
    pause: async () => {
        if ($('predict-button').disabled || resultColumnsLoading || predictionFiles.some(item => item.loading)) {
            throw new Error('Chờ tác vụ dữ liệu hiện tại hoàn tất trước khi xem bản nháp');
        }
        invalidateMapPreview(); ++predictionTableVersion;
        await window.workspacePersistence.pausePreview();
    },
    resume: () => window.workspacePersistence.resumePreview(),
    changed: () => updateAssistantHistory(),
});
const historyBar = document.createElement('div');
historyBar.className = 'assistant-history-bar';
historyBar.innerHTML = `<span role="status" aria-live="polite">Lịch sử chỉnh sửa AI</span>
    <button type="button" data-action="confirm" hidden>Xác nhận thay đổi</button>
    <button type="button" data-action="discard" hidden>Bỏ bản nháp</button>
    <button type="button" data-action="undo" disabled>Hoàn tác</button>
    <button type="button" data-action="redo" disabled>Làm lại</button>`;
document.querySelector('.workspace-header').append(historyBar);
function updateAssistantHistory() {
    if (typeof historyBar === 'undefined') return;
    const { pending, busy, past, future } = assistantHistory;
    for (const action of ['confirm', 'discard']) {
        const button = historyBar.querySelector(`[data-action="${action}"]`);
        button.hidden = !pending; button.disabled = busy;
    }
    historyBar.querySelector('[data-action="undo"]').disabled = busy || !!pending || !past.length;
    historyBar.querySelector('[data-action="redo"]').disabled = busy || !!pending || !future.length;
    historyBar.querySelector('[role="status"]').textContent = busy ? 'Đang dựng bản nháp AI'
        : pending ? 'Bản nháp AI chưa xác nhận' : 'Lịch sử chỉnh sửa AI';
    // Leave tabs, map pan/zoom and the table available for inspection.
    document.querySelectorAll('.map-sidebar, .workspace-crs, #layer-inspector .style-editor')
        .forEach(node => { node.inert = busy || !!pending; });
    window.dispatchEvent(new Event('assistant-workspace-change'));
}
Object.assign(window.assistantWorkspace, {
    stage: change => assistantHistory.stage(() => window.assistantWorkspace.commit(change)),
    confirm: () => assistantHistory.confirm(),
    discard: () => assistantHistory.travel('discard'),
    hasDraft: () => !!assistantHistory.pending,
});
historyBar.addEventListener('click', async event => {
    const action = event.target.closest('button')?.dataset.action;
    if (!action) return;
    try {
        if (action === 'confirm') assistantHistory.confirm();
        else await assistantHistory.travel(action);
    } catch (error) { historyBar.querySelector('[role="status"]').textContent = error.message; }
});
