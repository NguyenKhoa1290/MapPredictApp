// DOM controller owned by the React assessment page.
export function installCore(ctx) {
  const {
    window,
    document,
    L,
    Basemaps,
    WorkspaceHistory,
    fetch,
    URL,
    setTimeout
  } = ctx;
  ctx.showStatus = function showStatus(id, message, error = false) {
    if (ctx.disposed) return;
    const element = ctx.$(id);
    element.textContent = message;
    element.className = `status-message ${error ? "text-danger" : "text-success"}`;
    window.workspacePersistence?.schedule();
  };
  ctx.api = async function api(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (ctx.disposed) throw new DOMException('Assessment has been disposed', 'AbortError');
    if (!response.ok) throw new Error(payload.error || `Yêu cầu thất bại (${response.status}).`);
    return payload;
  };
  ctx.fillSelect = function fillSelect(select, values) {
    const previous = select.value;
    select.replaceChildren();
    for (const value of values) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.append(option);
    }
    if (values.includes(previous)) select.value = previous;
  };
  ctx.crsDiagnosisText = function crsDiagnosisText(diagnostics) {
    const bounds = diagnostics.raw_bounds;
    const range = bounds ? `X ${Math.round(bounds[0])}–${Math.round(bounds[2])}, Y ${Math.round(bounds[1])}–${Math.round(bounds[3])}. ` : "";
    return `${range}File ${diagnostics.declared_crs ? `khai báo ${diagnostics.declared_crs}` : "không khai báo EPSG"}. Khi hiển thị sẽ dùng hệ tọa độ chung bạn chọn ở thanh trên.`;
  };
  ctx.offsetInput = function offsetInput(name, value) {
    const input = document.createElement("input");
    input.type = "number";
    input.step = "any";
    input.name = name;
    input.value = String(value);
    return input;
  };
  ctx.labeledControl = function labeledControl(text, control) {
    const label = document.createElement("label");
    label.append(document.createTextNode(text), control);
    return label;
  };
  ctx.updateCadOptions = function updateCadOptions() {
    ctx.invalidateMapPreview();
    for (const state of ctx.cadAnalysisCards) {
      state.entry.offsetX = state.card.querySelector('[name="cad_offset_x"]').value;
      state.entry.offsetY = state.card.querySelector('[name="cad_offset_y"]').value;
    }
    ctx.resetCadAnalysis();
    ctx.cadAnalysisCards = [];
    const container = ctx.$("cad-options");
    container.replaceChildren();
    for (const entry of ctx.cadFiles) {
      const {
        file
      } = entry;
      const card = document.createElement("div");
      card.className = "cad-option";
      const title = document.createElement("strong");
      title.textContent = file.name;
      card.append(title);
      const offsets = document.createElement("div");
      offsets.className = "offset-fields";
      const offsetX = ctx.offsetInput("cad_offset_x", entry.offsetX || 0);
      const offsetY = ctx.offsetInput("cad_offset_y", entry.offsetY || 0);
      offsets.append(ctx.labeledControl("Dịch X (m)", offsetX), ctx.labeledControl("Dịch Y (m)", offsetY));
      card.append(offsets);
      const analyze = document.createElement("button");
      analyze.type = "button";
      analyze.className = "cad-action";
      analyze.textContent = "Phân tích độ dịch";
      const result = document.createElement("div");
      result.className = "cad-analysis";
      result.setAttribute("role", "status");
      result.setAttribute("aria-live", "polite");
      const state = {
        card,
        entry,
        analyze,
        result,
        version: 0,
        controller: null
      };
      ctx.cadAnalysisCards.push(state);
      analyze.addEventListener("click", () => ctx.analyzeCad(file, offsetX, offsetY, state));
      offsetX.addEventListener("input", ctx.clearCadPreview);
      offsetY.addEventListener("input", ctx.clearCadPreview);
      const remove = ctx.sourceRemoveButton(entry, "cad");
      card.append(analyze, ctx.sourceExportButton(entry), remove, result);
      container.append(card);
    }
    window.workspacePersistence?.schedule();
  };
  ctx.appendSourceFiles = function appendSourceFiles(collection, files) {
    for (const file of files) {
      const key = JSON.stringify([file.name, file.size, file.lastModified]);
      if (!collection.some(entry => entry.key === key)) {
        collection.push({
          file,
          key,
          id: crypto.randomUUID()
        });
      }
    }
  };
  ctx.sourceRemoveButton = function sourceRemoveButton(entry, kind) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "cad-action source-remove";
    button.textContent = "Gỡ file";
    button.addEventListener("click", () => {
      ++ctx.mapRequestVersion;
      ctx.mapRequestController?.abort();
      ctx.$("map-button").disabled = false;
      ctx.$("map-button").textContent = "Hiển thị trên bản đồ";
      if (kind === "cad") {
        ctx.cadFiles = ctx.cadFiles.filter(source => source !== entry);
        ctx.updateCadOptions();
      } else {
        ctx.predictionFiles = ctx.predictionFiles.filter(source => source !== entry);
        ctx.updatePredictionSources();
      }
      ctx.renderMap(ctx.overlays.filter(overlay => overlay.item.source_id !== entry.id).map(overlay => overlay.item));
    });
    return button;
  };
  ctx.sourceExportButton = function sourceExportButton(entry) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'cad-action';
    button.textContent = 'Xuất file';
    button.addEventListener('click', () => {
      const url = URL.createObjectURL(entry.file),
        link = document.createElement('a');
      link.href = url;
      link.download = entry.file.name;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    return button;
  };
  ctx.commonPredictionColumns = function commonPredictionColumns() {
    return ctx.predictionFiles.length && ctx.predictionFiles.every(entry => entry.columns) ? ctx.predictionFiles[0].columns.filter(name => ctx.predictionFiles.every(entry => entry.columns.includes(name))) : [];
  };
  ctx.individualPredictionJoins = function individualPredictionJoins() {
    return new Set(ctx.predictionFiles.map(entry => entry.file.name.split(".").pop().toLowerCase())).size > 1 || ctx.predictionFiles.length > 0 && ctx.predictionFiles.every(entry => entry.columns) && !ctx.commonPredictionColumns().length;
  };
  ctx.updatePredictionSources = function updatePredictionSources() {
    ctx.invalidateMapPreview();
    ctx.gpkgJoinPreference = ctx.$("gpkg-join").value || ctx.gpkgJoinPreference;
    const list = ctx.$("prediction-sources");
    list.replaceChildren();
    for (const entry of ctx.predictionFiles) {
      const row = document.createElement("div");
      row.className = "prediction-source";
      const name = document.createElement("span");
      name.textContent = `${entry.file.name}${entry.error ? ` · ${entry.error}` : ""}`;
      row.append(name, ctx.sourceExportButton(entry), ctx.sourceRemoveButton(entry, "prediction"));
      if (entry.diagnostics?.format === "dxf") {
        const note = document.createElement("p");
        note.className = "field-note";
        note.textContent = `${entry.diagnostics.cell_count} ô kín; ${entry.diagnostics.identified_count} ô có mã duy nhất. ` + "grid_id đọc từ nhãn TEXT/MTEXT trong ô, không phải thuộc tính tenlodat gốc. " + "Không ghép theo thứ tự ô hay cao độ POINT.";
        row.append(note);
        for (const [warning, count] of Object.entries(entry.diagnostics.warnings || {})) {
          const message = document.createElement("p");
          message.className = "field-note text-danger";
          message.textContent = `${warning}: ${count}`;
          row.append(message);
        }
      }
      if (ctx.individualPredictionJoins() && entry.columns) {
        const select = document.createElement("select");
        select.className = "prediction-source-join";
        select.setAttribute("aria-label", `Cột ghép ${entry.file.name}`);
        ctx.fillSelect(select, entry.columns);
        const preferred = entry.joinColumn || entry.suggestedJoin || ctx.gpkgJoinPreference;
        if (entry.columns.includes(preferred)) select.value = preferred;
        entry.joinColumn = select.value;
        select.addEventListener("change", () => {
          entry.joinColumn = select.value;
        });
        row.append(ctx.labeledControl("Cột ghép trong file", select));
      }
      list.append(row);
    }
    const columns = ctx.commonPredictionColumns();
    ctx.fillSelect(ctx.$("gpkg-join"), columns);
    if (columns.includes(ctx.gpkgJoinPreference)) ctx.$("gpkg-join").value = ctx.gpkgJoinPreference;else if (columns.includes("grid_id")) ctx.$("gpkg-join").value = "grid_id";
    ctx.$("common-layer-join").hidden = ctx.individualPredictionJoins();
    ctx.$("gpkg-join").disabled = ctx.individualPredictionJoins();
    ctx.$("prediction-crs-info").textContent = ctx.predictionFiles.length ? `${ctx.predictionFiles.length} file lưới DXF/GPKG. ${ctx.individualPredictionJoins() ? "Chọn cột ghép riêng ở từng file." : "Các file dùng chung cột ghép."} Dùng chung hệ tọa độ nguồn, CSV và độ dịch X/Y. DXF chưa có kết quả vẫn xem được đường ô.` : "";
    ctx.updateJoinVisibility();
    window.workspacePersistence?.schedule();
  };
  ctx.clearCadPreview = function clearCadPreview() {
    if (ctx.map && ctx.cadPreview) ctx.map.removeLayer(ctx.cadPreview);
    ctx.cadPreview = null;
  };
  ctx.resetCadAnalysis = function resetCadAnalysis() {
    ctx.clearCadPreview();
    for (const state of ctx.cadAnalysisCards) {
      ++state.version;
      state.controller?.abort();
      state.result.replaceChildren();
      state.result.removeAttribute("aria-busy");
      state.analyze.disabled = false;
      state.analyze.textContent = "Phân tích độ dịch";
    }
  };
  ctx.analyzeCad = async function analyzeCad(file, offsetX, offsetY, state) {
    const sourceCrs = ctx.sharedSourceCrs();
    const {
      card,
      analyze,
      result
    } = state;
    ctx.clearCadPreview();
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
      const payload = await ctx.api("/api/cad-diagnostics", {
        method: "POST",
        body: form,
        signal: state.controller.signal
      });
      if (!card.isConnected || version !== state.version || sourceCrs !== ctx.sharedSourceCrs()) return;
      result.replaceChildren();
      const message = document.createElement("p");
      message.textContent = payload.message;
      result.append(message);
      const candidate = payload.candidate;
      if (!candidate || payload.status !== "suggested") return;
      const details = document.createElement("p");
      details.className = "cad-analysis-details";
      details.textContent = `${payload.source_crs} · ΔX ${candidate.offset_x.toFixed(6)} m · ΔY ${candidate.offset_y.toFixed(6)} m. ` + `${candidate.support_points} đỉnh đối chiếu; sai lệch phép dịch ≤ ${candidate.max_residual_m.toFixed(6)} m. ` + `Tâm dự kiến: ${candidate.latitude.toFixed(6)}° Bắc, ${candidate.longitude.toFixed(6)}° Đông.`;
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
        ctx.clearCadPreview();
        ctx.initializeMap();
        if (!ctx.map) return;
        const [west, south, east, north] = candidate.preview_bounds;
        const bounds = L.latLngBounds([[south, west], [north, east]]);
        const marker = L.circleMarker([candidate.latitude, candidate.longitude], {
          radius: 6,
          color: "#b45309",
          fillOpacity: 1
        });
        const caption = document.createElement("span");
        caption.textContent = `Khung phạm vi đề xuất: ${file.name}. Chưa áp dụng độ dịch.`;
        marker.bindPopup(caption);
        ctx.cadPreview = L.layerGroup([L.rectangle(bounds, {
          color: "#b45309",
          weight: 2,
          dashArray: "7 5",
          fillOpacity: 0.08,
          interactive: false
        }), marker]).addTo(ctx.map);
        ctx.map.fitBounds(bounds, {
          padding: [32, 32],
          maxZoom: 17
        });
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
        ctx.invalidateMapPreview();
        // This replaces absolute offsets, never adds the proposal twice.
        offsetX.value = candidate.offset_x.toFixed(6);
        offsetY.value = candidate.offset_y.toFixed(6);
        ctx.clearCadPreview();
        applied.textContent = "Đã điền X/Y riêng cho file này. Nhấn Hiển thị trên bản đồ để nạp lại layer. EPSG chung không thay đổi.";
      });
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "cad-action";
      cancel.textContent = "Đóng đề xuất";
      cancel.addEventListener("click", () => {
        ctx.clearCadPreview();
        result.replaceChildren();
      });
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
  };
  ctx.sharedSourceCrs = function sharedSourceCrs() {
    return (ctx.$("project-crs").value === "custom" ? ctx.$("project-crs-custom").value.trim() : ctx.$("project-crs").value).toUpperCase();
  };
  ctx.applySharedCrs = function applySharedCrs(reload = false) {
    const custom = ctx.$("project-crs").value === "custom";
    ctx.$("project-crs-custom").hidden = !custom;
    ctx.$("project-crs-custom").disabled = !custom;
    ctx.$("project-crs-custom").required = custom;
    const crs = ctx.sharedSourceCrs();
    if (ctx.$("source-crs").value !== crs) ctx.resetCadAnalysis();
    ctx.$("source-crs").value = crs;
    try {
      if (/^EPSG:\d{4,6}$/.test(crs)) localStorage.setItem(ctx.sharedCrsStorageKey, crs);else localStorage.removeItem(ctx.sharedCrsStorageKey);
    } catch {/* Browser storage is optional. */}
    if (reload && ctx.overlays.length && /^EPSG:\d{4,6}$/.test(crs)) {
      ctx.$("map-form").requestSubmit();
    } else if (!ctx.overlays.length) {
      ctx.$("map-crs-status").textContent = crs ? `Hệ chung: ${crs}` : "Chưa chọn hệ tọa độ chung";
    }
  };
  ctx.resultsCsvFile = function resultsCsvFile(rows, columns = [...new Set(rows.flatMap(row => Object.keys(row)))]) {
    const quote = value => `"${String(value ?? "").replace(/"/g, '""')}"`;
    const lines = [columns.map(quote).join(","), ...rows.map(row => columns.map(key => quote(row[key])).join(","))];
    return new File(["\ufeff", lines.join("\r\n")], "KetQua.csv", {
      type: "text/csv;charset=utf-8"
    });
  };
  ctx.renderPredictionTable = function renderPredictionTable(rows, isResult, total = rows.length, columns = [...new Set(rows.flatMap(row => Object.keys(row)))], page = 0) {
    ctx.predictionView = {
      rows,
      isResult,
      total,
      columns,
      page: Math.max(0, Math.min(Number.isInteger(page) ? page : 0, Math.ceil(rows.length / ctx.PREDICTION_PAGE_SIZE) - 1))
    };
    ctx.updateCsvControls();
    window.workspacePersistence?.schedule();
    const hasData = rows.length > 0 || columns.length > 0;
    ctx.$("prediction-empty").hidden = hasData;
    ctx.$("prediction-table-scroll").hidden = !hasData;
    ctx.$("prediction-export").hidden = !hasData;
    if (ctx.predictionDownloadUrl) URL.revokeObjectURL(ctx.predictionDownloadUrl);
    const exportFile = isResult ? ctx.resultsCsvFile(rows, columns) : ctx.$('csv-file').files[0] || ctx.$('result-file').files[0] || ctx.resultsCsvFile(rows, columns);
    // Keep one File per rendered result. Assistant preview/apply compares file
    // identity and must receive the full result, not the uploaded input preview.
    ctx.predictionViewCsv = isResult && hasData ? exportFile : null;
    ctx.predictionDownloadUrl = hasData ? URL.createObjectURL(exportFile) : null;
    ctx.$("prediction-export").href = ctx.predictionDownloadUrl || "#";
    ctx.$("prediction-export").download = exportFile.name;
    ctx.$("prediction-title").textContent = hasData ? isResult ? "Kết quả dự đoán" : "Dữ liệu đầu vào" : "Bảng dữ liệu";
    const table = ctx.$("prediction-table");
    table.replaceChildren();
    if (!hasData) {
      ctx.$("prediction-count").textContent = "Chưa có dữ liệu để hiển thị.";
      ctx.$("prediction-pager").hidden = true;
      return;
    }
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
    ctx.renderPredictionPage();
  };
  ctx.renderPredictionPage = function renderPredictionPage() {
    const {
      rows,
      isResult,
      total,
      columns,
      page
    } = ctx.predictionView;
    const start = page * ctx.PREDICTION_PAGE_SIZE;
    const body = document.createElement("tbody");
    for (const [index, row] of rows.slice(start, start + ctx.PREDICTION_PAGE_SIZE).entries()) {
      const tr = document.createElement("tr");
      const rowNumber = document.createElement("th");
      rowNumber.className = "row-number";
      rowNumber.scope = "row";
      rowNumber.textContent = String(start + index + 1);
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
    const table = ctx.$("prediction-table");
    table.querySelector("tbody")?.remove();
    table.append(body);
    const pages = Math.max(1, Math.ceil(rows.length / ctx.PREDICTION_PAGE_SIZE));
    ctx.$("prediction-count").textContent = rows.length > ctx.PREDICTION_PAGE_SIZE ? `Dòng ${(start + 1).toLocaleString("vi-VN")}–${Math.min(start + ctx.PREDICTION_PAGE_SIZE, rows.length).toLocaleString("vi-VN")} / ${total.toLocaleString("vi-VN")} · ${columns.length} cột` : `${total.toLocaleString("vi-VN")} dòng · ${columns.length} cột`;
    ctx.$("prediction-pager").hidden = pages <= 1;
    ctx.$("prediction-page-prev").disabled = page === 0;
    ctx.$("prediction-page-next").disabled = page + 1 >= pages;
    ctx.$("prediction-page-number").value = String(page + 1);
    ctx.$("prediction-page-number").max = String(pages);
    ctx.$("prediction-page-total").textContent = `/ ${pages.toLocaleString("vi-VN")}`;
    ctx.$("prediction-table-scroll").scrollTo(0, 0);
  };
  ctx.selectPredictionPage = function selectPredictionPage(page) {
    if (!ctx.predictionView) return;
    const pages = Math.max(1, Math.ceil(ctx.predictionView.rows.length / ctx.PREDICTION_PAGE_SIZE));
    ctx.predictionView = {
      ...ctx.predictionView,
      page: Math.max(0, Math.min(Number.isFinite(page) ? Math.trunc(page) : 0, pages - 1))
    };
    ctx.renderPredictionPage();
    window.workspacePersistence?.schedule();
  };
  ctx.renderResults = function renderResults(rows, display = true) {
    ctx.invalidateMapPreview();
    ctx.predictionRows = rows;
    if (display) ctx.renderPredictionTable(rows, true);
    const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
    ctx.fillSelect(ctx.$("csv-join"), columns.filter(name => name !== "Y"));
    ctx.updateJoinVisibility();
  };
  ctx.updateJoinVisibility = function updateJoinVisibility() {
    ctx.$("join-controls").hidden = !ctx.predictionFiles.length;
    ctx.$("join-preview-button").hidden = !ctx.predictionFiles.length;
  };
  ctx.updateBasemapLabels = function updateBasemapLabels() {
    const satellite = ctx.activeBasemap === "satellite";
    ctx.$("basemap-labels").disabled = !satellite;
    ctx.$("basemap-labels-note").textContent = satellite ? "Nhãn đường và địa danh Esri. Không bật nhãn chữ trong DXF." : "Nền đường phố đã có nhãn riêng; công tắc nhãn chỉ áp dụng cho vệ tinh.";
    if (!ctx.map || !ctx.referenceLabels) return;
    if (satellite && ctx.$("basemap-labels").checked) ctx.referenceLabels.addTo(ctx.map);else ctx.map.removeLayer(ctx.referenceLabels);
  };
  ctx.selectBasemap = function selectBasemap(value) {
    if (!ctx.map || !ctx.basemapLayers) return;
    const next = Object.hasOwn(ctx.basemapLayers, value) ? value : "satellite";
    if (ctx.activeBasemap !== next) {
      if (ctx.activeBasemap) ctx.map.removeLayer(ctx.basemapLayers[ctx.activeBasemap]);
      ctx.activeBasemap = next;
      ctx.basemapLayers[next].addTo(ctx.map);
    }
    ctx.$("basemap-select").value = next;
    ctx.$("map-basemap-status").textContent = next === "satellite" ? "Vệ tinh Esri" : "Đường phố OpenStreetMap";
    ctx.$("basemap-message").textContent = "";
    ctx.updateBasemapLabels();
    try {
      localStorage.setItem(ctx.basemapStorageKey, next);
    } catch {/* Optional preference. */}
  };
  ctx.initializeMap = function initializeMap() {
    if (ctx.map) {
      ctx.map.invalidateSize();
      if (!ctx.$("map-panel").hidden && ctx.pendingMapBounds) {
        ctx.map.fitBounds(ctx.pendingMapBounds, {
          padding: [24, 24],
          maxZoom: 17
        });
        ctx.pendingMapBounds = null;
      }
      return;
    }
    if (!window.L) {
      ctx.showStatus("map-message", "Không tải được Leaflet. Kiểm tra kết nối mạng.", true);
      return;
    }
    ctx.map = L.map(ctx.$("leafletMap"), {
      ...Basemaps.motionOptions(),
      zoomControl: true,
      preferCanvas: true,
      renderer: L.canvas({
        padding: 0.3
      }),
      minZoom: 2,
      maxZoom: Basemaps.MAX_ZOOM
    }).setView([16.2, 107.5], 6);
    ctx.basemapLayers = {
      // blankTile=false makes missing Esri coverage detectable (404), rather
      // than displaying the provider's grey "Map data not yet available" image.
      satellite: Basemaps.createFallbackLayer(L, "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?blankTile=false", {
        attribution: 'Imagery &copy; <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics, and the GIS User Community'
      }),
      streets: Basemaps.createFallbackLayer(L, "https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        nativeMaxZoom: 19,
        fallbackDepth: 0,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      })
    };
    for (const [key, layer] of Object.entries(ctx.basemapLayers)) {
      const failedTiles = new Set();
      const tileKey = ({
        coords
      }) => `${coords.z}:${coords.x}:${coords.y}`;
      layer.on("tileerror", event => {
        failedTiles.add(tileKey(event));
        if (ctx.activeBasemap === key) ctx.$("basemap-message").textContent = "Không tải được một phần nền bản đồ. Kiểm tra Internet hoặc đổi nền; layer của bạn vẫn được giữ.";
      });
      layer.on("tileload tileunload", event => failedTiles.delete(tileKey(event)));
      layer.on("load", () => {
        if (ctx.activeBasemap === key && !failedTiles.size) ctx.$("basemap-message").textContent = "";
      });
    }
    // Keep basemap names above user geometry without intercepting feature clicks.
    const labelsPane = ctx.map.createPane("referenceLabels");
    labelsPane.style.zIndex = "625";
    labelsPane.style.pointerEvents = "none";
    ctx.referenceLabels = L.layerGroup(["World_Transportation", "World_Boundaries_and_Places"].map(service => Basemaps.createFallbackLayer(L, `https://services.arcgisonline.com/ArcGIS/rest/services/Reference/${service}/MapServer/tile/{z}/{y}/{x}?blankTile=false`, {
      pane: "referenceLabels",
      nativeMaxZoom: 18,
      attribution: 'Labels &copy; <a href="https://www.esri.com/">Esri</a>, HERE, Garmin'
    })));
    try {
      ctx.$("basemap-labels").checked = localStorage.getItem(ctx.labelsStorageKey) !== "false";
    } catch {/* Keep labels enabled when browser storage is unavailable. */}
    let preferredBasemap = "satellite";
    try {
      preferredBasemap = localStorage.getItem(ctx.basemapStorageKey) || preferredBasemap;
    } catch {/* Default imagery. */}
    ctx.selectBasemap(preferredBasemap);
  };
  ctx.renderMap = function renderMap(layers, savedLayers = null, restoring = false) {
    ctx.clearCadPreview();
    ctx.initializeMap();
    if (!ctx.map) return;
    ctx.renderManagedLayers(layers, savedLayers);
    for (const overlay of ctx.overlays) {
      const entry = [...ctx.cadFiles, ...ctx.predictionFiles].find(item => item.id === overlay.item.source_id);
      overlay.sourceKey = restoring ? savedLayers?.find(item => item.id === overlay.id)?.sourceKey || entry?.key : entry?.key;
    }
    window.workspacePersistence?.schedule();
  };
  ctx.updateCsvControls = function updateCsvControls() {
    const history = window.assistantWorkspace?.historyState?.();
    for (const button of document.querySelectorAll('[data-remove-csv]')) {
      const input = ctx.$(button.dataset.removeCsv);
      button.hidden = !input.files.length;
      button.disabled = ctx.$('predict-button').disabled || !!history?.pending || !!history?.busy;
      const label = document.querySelector(`[data-file-label="${input.id}"]`);
      if (label) label.textContent = input.files[0]?.name || label.dataset.defaultLabel || 'Chưa chọn file';
    }
  };
  ctx.readPredictionSources = async function readPredictionSources() {
    const pending = ctx.predictionFiles.filter(entry => !entry.columns && !entry.loading);
    pending.forEach(entry => {
      entry.loading = true;
    });
    ctx.updatePredictionSources();
    await Promise.all(pending.map(async entry => {
      const form = new FormData();
      form.append("layer", entry.file);
      try {
        const payload = await ctx.api("/api/prediction-columns", {
          method: "POST",
          body: form
        });
        entry.columns = payload.columns;
        entry.diagnostics = payload.diagnostics;
        entry.suggestedJoin = payload.suggested_join;
        entry.error = null;
      } catch (error) {
        entry.error = error.message;
      } finally {
        entry.loading = false;
        ctx.updatePredictionSources();
      }
    }));
  };
  ctx.invalidateMapPreview = function invalidateMapPreview() {
    ++ctx.mapRequestVersion;
    ctx.mapRequestController?.abort();
    ctx.joinPreview.invalidate();
    ctx.$("map-button").disabled = false;
    ctx.$("map-button").textContent = "Hiển thị trên bản đồ";
  };
  ctx.applyMapPayload = function applyMapPayload(payload) {
    ctx.renderMap(payload.layers);
    ctx.$("map-crs-status").textContent = `Hệ chung: ${payload.source_crs}`;
    const summaries = payload.layers.filter(layer => layer.data.join_summary).map(layer => {
      const summary = layer.data.join_summary;
      return summary.results_applied ? `${layer.name}: ${summary.matched}/${summary.total} ô khớp, ${summary.unmatched} ô chưa tô màu` : `${layer.name}: ${summary.total} ô, chưa áp dụng kết quả dự đoán`;
    });
    ctx.showStatus("map-message", `Đã tải ${payload.layers.length} layer theo ${payload.source_crs} ${summaries.join(" · ")}`);
  };
  ctx.updateAssistantHistory = function updateAssistantHistory() {
    if (typeof ctx.historyBar === 'undefined') return;
    const {
      pending,
      busy,
      past,
      future
    } = ctx.assistantHistory;
    try {
      const key = 'mapPredict.assistant.timeline.v1';
      const cursor = JSON.stringify({
        undo: past.length,
        redo: future.length,
        storage: 'IndexedDB'
      });
      if (localStorage.getItem(key) !== cursor) localStorage.setItem(key, cursor);
    } catch {/* The atomic workspace store remains authoritative. */}
    for (const action of ['confirm', 'discard']) {
      const button = ctx.historyBar.querySelector(`[data-action="${action}"]`);
      button.hidden = !pending;
      button.disabled = busy;
    }
    ctx.historyBar.querySelector('[data-action="undo"]').disabled = busy || !!pending || !past.length;
    ctx.historyBar.querySelector('[data-action="redo"]').disabled = busy || !!pending || !future.length;
    ctx.historyBar.querySelector('[role="status"]').textContent = busy ? 'Đang dựng bản nháp AI' : pending ? 'Bản nháp AI chưa xác nhận' : 'Lịch sử chỉnh sửa AI';
    // Leave tabs, map pan/zoom and the table available for inspection.
    document.querySelectorAll('.map-sidebar, .workspace-crs, #layer-inspector .style-editor').forEach(node => {
      node.inert = busy || !!pending;
    });
    window.dispatchEvent(new Event('assistant-workspace-change'));
    ctx.updateCsvControls();
  };
  ctx.$ = id => document.getElementById(id);
  ctx.predictionRows = [];
  ctx.predictionTableVersion = 0;
  ctx.predictionView = null;
  ctx.predictionViewCsv = null;
  ctx.predictionDownloadUrl = null;
  ctx.PREDICTION_PAGE_SIZE = 200;
  ctx.map = null;
  ctx.referenceLabels = null;
  ctx.basemapLayers = null;
  ctx.activeBasemap = null;
  ctx.cadPreview = null;
  ctx.cadAnalysisCards = [];
  ctx.cadFiles = [];
  ctx.predictionFiles = [];
  ctx.gpkgJoinPreference = "";
  ctx.overlays = [];
  ctx.pendingMapBounds = null;
  ctx.mapRequestVersion = 0;
  ctx.mapRequestController = null;
  ctx.resultColumnsLoading = false;
  ctx.resultColumnsVersion = 0;
  ctx.joinPreview = window.JoinPreview.create({
    container: ctx.$("join-preview"),
    button: ctx.$("join-apply"),
    apply: ctx.applyMapPayload
  });
  ctx.sharedCrsStorageKey = "mapPredict.sharedCrs";
  ctx.labelsStorageKey = "mapPredict.labelsVisible";
  ctx.basemapStorageKey = "mapPredict.basemap";
  try {
    const savedCrs = localStorage.getItem(ctx.sharedCrsStorageKey);
    if (savedCrs && /^EPSG:\d{4,6}$/.test(savedCrs)) {
      const listed = [...ctx.$("project-crs").options].some(option => option.value === savedCrs);
      ctx.$("project-crs").value = listed ? savedCrs : "custom";
      if (!listed) ctx.$("project-crs-custom").value = savedCrs;
    }
  } catch {/* Continue with an unselected CRS if storage is unavailable. */}
  ctx.applySharedCrs();
  ctx.$("project-crs").addEventListener("change", () => ctx.applySharedCrs(true));
  ctx.$("project-crs-custom").addEventListener("change", () => ctx.applySharedCrs(true));
  ctx.$("prediction-page-prev").addEventListener("click", () => ctx.selectPredictionPage(ctx.predictionView.page - 1));
  ctx.$("prediction-page-next").addEventListener("click", () => ctx.selectPredictionPage(ctx.predictionView.page + 1));
  ctx.$("prediction-page-number").addEventListener("change", event => ctx.selectPredictionPage(Number(event.target.value) - 1));
  ctx.$("prediction-page-number").addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      ctx.selectPredictionPage(Number(event.target.value) - 1);
    }
  });
  ctx.$("basemap-select").addEventListener("change", event => ctx.selectBasemap(event.target.value));
  ctx.$("basemap-labels").addEventListener("change", event => {
    const visible = event.target.checked;
    ctx.updateBasemapLabels();
    try {
      localStorage.setItem(ctx.labelsStorageKey, String(visible));
    } catch {/* Toggling labels does not require browser storage. */}
  });
  for (const button of document.querySelectorAll('[data-remove-csv]')) {
    button.addEventListener('click', async () => {
      const history = window.assistantWorkspace?.historyState?.();
      if (ctx.$('predict-button').disabled || history?.pending || history?.busy) return;
      const id = button.dataset.removeCsv;
      ctx.$(id).files = new DataTransfer().files;
      if (id === 'csv-file') {
        ++ctx.predictionTableVersion;
        ctx.renderResults([], false);
        ctx.renderPredictionTable([], false);
        ctx.showStatus('predict-message', 'Đã xóa file CSV và bảng dữ liệu');
      } else if (!ctx.$('csv-file').files.length && !ctx.predictionView.isResult) {
        ++ctx.predictionTableVersion;
        ctx.renderPredictionTable([], false);
      }
      ctx.invalidateMapPreview();
      ctx.$('result-file').dispatchEvent(new Event('change', {
        bubbles: true
      }));
      ctx.updateCsvControls();
      window.workspacePersistence?.schedule();
      await window.workspacePersistence?.flush();
    });
  }
  for (const input of document.querySelectorAll('input[type="file"]')) {
    input.addEventListener("change", () => {
      ctx.updateCsvControls();
      const label = document.querySelector(`[data-file-label="${input.id}"]`);
      if (label) label.textContent = input.files[0]?.name || label.dataset.defaultLabel || "Chưa chọn file";
      if (input.id === "cad-file") {
        ctx.appendSourceFiles(ctx.cadFiles, [...input.files]);
        input.value = "";
        ctx.updateCadOptions();
      }
    });
  }
  for (const [tabId, panelId, otherTabId, otherPanelId] of [["predict-tab", "predict-panel", "map-tab", "map-panel"], ["map-tab", "map-panel", "predict-tab", "predict-panel"]]) {
    ctx.$(tabId).addEventListener("click", () => {
      ctx.$(panelId).hidden = false;
      ctx.$(otherPanelId).hidden = true;
      ctx.$(tabId).classList.add("active");
      ctx.$(otherTabId).classList.remove("active");
      ctx.$(tabId).setAttribute("aria-selected", "true");
      ctx.$(otherTabId).setAttribute("aria-selected", "false");
      if (panelId === "map-panel") setTimeout(ctx.initializeMap, 0);
      document.body.classList.toggle("map-mode", panelId === "map-panel");
    });
  }
  ctx.$("csv-file").addEventListener("change", async event => {
    const version = ++ctx.predictionTableVersion;
    const file = event.target.files[0];
    if (!file) {
      ctx.renderResults(ctx.predictionRows);
      ctx.showStatus("predict-message", "");
      return;
    }
    const form = new FormData();
    form.append("csv", file);
    ctx.showStatus("predict-message", "Đang đọc dữ liệu CSV...");
    try {
      const payload = await ctx.api("/api/preview-csv", {
        method: "POST",
        body: form
      });
      if (version !== ctx.predictionTableVersion) return;
      ctx.renderPredictionTable(payload.rows, false, payload.count);
      ctx.showStatus("predict-message", `Đã nạp ${payload.count.toLocaleString("vi-VN")} dòng. Sẵn sàng dự đoán.`);
    } catch (error) {
      if (version !== ctx.predictionTableVersion) return;
      ctx.renderPredictionTable([], false);
      ctx.showStatus("predict-message", `Lỗi: ${error.message}`, true);
    }
  });
  ctx.$("predict-form").addEventListener("submit", async event => {
    event.preventDefault();
    const version = ++ctx.predictionTableVersion;
    const form = new FormData(event.currentTarget);
    const inputs = [...event.currentTarget.querySelectorAll('input[type="file"]')];
    inputs.forEach(input => {
      input.disabled = true;
    });
    const button = ctx.$("predict-button");
    button.disabled = true;
    button.textContent = "Đang xử lý...";
    ctx.$("prediction-result").setAttribute("aria-busy", "true");
    ctx.showStatus("predict-message", "");
    try {
      const payload = await ctx.api("/api/predict", {
        method: "POST",
        body: form
      });
      if (version !== ctx.predictionTableVersion) return;
      ctx.renderResults(payload.rows);
      ctx.showStatus("predict-message", `Đã dự đoán ${payload.rows.length.toLocaleString("vi-VN")} dòng. Có thể xuất CSV ở bảng bên phải.`);
    } catch (error) {
      ctx.showStatus("predict-message", `Lỗi: ${error.message}`, true);
    } finally {
      button.disabled = false;
      button.textContent = "Bắt đầu dự đoán";
      inputs.forEach(input => {
        input.disabled = false;
      });
      ctx.updateCsvControls();
      ctx.$("prediction-result").removeAttribute("aria-busy");
    }
  });
  ctx.$("layer-file").addEventListener("change", async event => {
    ctx.appendSourceFiles(ctx.predictionFiles, [...event.target.files]);
    event.target.value = "";
    await ctx.readPredictionSources();
  });
  ctx.$("result-file").addEventListener("change", async event => {
    const version = ++ctx.resultColumnsVersion;
    const file = event.target.files[0];
    ctx.resultColumnsLoading = !!file;
    if (!file) {
      ctx.fillSelect(ctx.$("csv-join"), ctx.predictionRows.length ? Object.keys(ctx.predictionRows[0]).filter(name => name !== "Y") : []);
      return;
    }
    const form = new FormData();
    form.append("result", file);
    try {
      const payload = await ctx.api("/api/result-columns", {
        method: "POST",
        body: form
      });
      if (version !== ctx.resultColumnsVersion) return;
      ctx.fillSelect(ctx.$("csv-join"), payload.columns);
      ctx.showStatus("map-message", `Đã nạp file kết quả: ${file.name}`);
    } catch (error) {
      if (version !== ctx.resultColumnsVersion) return;
      ctx.fillSelect(ctx.$("csv-join"), []);
      ctx.showStatus("map-message", `Lỗi: ${error.message}`, true);
    } finally {
      if (version === ctx.resultColumnsVersion) ctx.resultColumnsLoading = false;
    }
  });
  ctx.$("join-preview-button").addEventListener("click", () => ctx.$("map-form").requestSubmit());
  for (const event of ["input", "change"]) {
    ctx.$("map-form").addEventListener(event, ctx.invalidateMapPreview);
    ctx.$("project-crs").addEventListener(event, ctx.invalidateMapPreview, true);
    ctx.$("project-crs-custom").addEventListener(event, ctx.invalidateMapPreview, true);
  }
  ctx.$("map-form").addEventListener("submit", async event => {
    event.preventDefault();
    const version = ++ctx.mapRequestVersion;
    ctx.mapRequestController?.abort();
    ctx.mapRequestController = new AbortController();
    ctx.$("source-crs").value = ctx.sharedSourceCrs();
    const button = ctx.$("map-button");
    button.disabled = true;
    button.textContent = "Đang tải bản đồ...";
    ctx.showStatus("map-message", "");
    try {
      ctx.joinPreview.invalidate();
      if (ctx.resultColumnsLoading) throw new Error("Chờ đọc xong file kết quả CSV trước khi ghép");
      const form = new FormData(event.currentTarget);
      if (ctx.predictionFiles.length && !ctx.$("result-file").files.length && ctx.predictionRows.length) {
        form.set("result", ctx.resultsCsvFile(ctx.predictionRows));
      }
      if (ctx.predictionFiles.some(entry => entry.loading || !entry.columns)) {
        throw new Error("Chờ đọc xong lưới DXF/GPKG hoặc gỡ file đang báo lỗi trước khi hiển thị.");
      }
      form.delete("cad");
      form.delete("layer");
      for (const entry of ctx.cadFiles) {
        form.append("cad", entry.file);
        form.append("cad_id", entry.id);
      }
      for (const entry of ctx.predictionFiles) {
        form.append("layer", entry.file);
        form.append("layer_id", entry.id);
        form.append("layer_join", ctx.individualPredictionJoins() ? entry.joinColumn : ctx.$("gpkg-join").value);
      }
      const payload = await ctx.api("/api/map", {
        method: "POST",
        body: form,
        signal: ctx.mapRequestController.signal
      });
      if (version !== ctx.mapRequestVersion) return;
      if (payload.layers.some(layer => layer.data.join_summary?.results_applied)) {
        ctx.joinPreview.show(payload);
        ctx.showStatus("map-message", "Đã xem trước ghép kết quả, chọn Áp dụng kết quả lên bản đồ sau khi kiểm tra");
      } else ctx.applyMapPayload(payload);
    } catch (error) {
      if (version !== ctx.mapRequestVersion || error.name === "AbortError") return;
      ctx.showStatus("map-message", `Lỗi: ${error.message}`, true);
    } finally {
      if (version === ctx.mapRequestVersion) {
        button.disabled = false;
        button.textContent = "Hiển thị trên bản đồ";
      }
    }
  });
  ctx.initializeMap();
  ctx.$('back-to-projects').addEventListener('click', async event => {
    if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const destination = event.currentTarget.href;
    await window.workspacePersistence?.flush();
    ctx.navigate('/projects');
  });

  // Project resources are the assistant's inputs, not separate chat attachments.
  window.assistantWorkspace = {
    sources() {
      return [...ctx.cadFiles.map(entry => ({
        ...entry,
        kind: 'cad'
      })), ...ctx.predictionFiles.map(entry => ({
        ...entry,
        kind: 'prediction'
      }))].filter(entry => entry.file.name.toLowerCase().endsWith('.dxf'));
    },
    tables() {
      return ['csv-file', 'result-file'].flatMap(id => ctx.$(id).files[0] ? [{
        id,
        file: ctx.$(id).files[0]
      }] : []);
    },
    csv(id = 'csv-file') {
      return ctx.$(id)?.files[0] || null;
    },
    version() {
      return `${ctx.predictionTableVersion}:${ctx.mapRequestVersion}:${ctx.resultColumnsVersion}:${ctx.sharedSourceCrs()}`;
    },
    crs() {
      return ctx.sharedSourceCrs();
    },
    context() {
      const scope = ctx.$('map-panel').hidden ? 'prediction' : 'map';
      if (scope === 'prediction') {
        const csvId = ctx.$('csv-file').files[0] ? 'csv-file' : 'result-file';
        return {
          scope,
          csvId,
          csv: ctx.predictionViewCsv || this.csv(csvId),
          resources: [],
          version: this.version()
        };
      }
      const resources = this.sources().filter(entry => ctx.overlays.some(overlay => overlay.visible && overlay.item.source_id === entry.id && overlay.sourceKey === entry.key && overlay.item.crs === ctx.sharedSourceCrs()));
      return {
        scope,
        csv: null,
        csvId: '',
        resources,
        version: this.version()
      };
    },
    async commit({
      sourceId,
      original,
      dxf,
      dxfs = [],
      rows,
      columns,
      csvId = 'csv-file'
    }) {
      if (!window.workspacePersistence?.ready) throw new Error('Workspace chưa khôi phục xong, hãy chờ hoặc kiểm tra trạng thái bản lưu');
      const entry = [...ctx.cadFiles, ...ctx.predictionFiles].find(item => item.id === sourceId);
      if (sourceId && (!entry || entry.file !== original)) throw new Error('File DXF đã thay đổi, hãy tạo lại bản xem trước');
      const changes = [...dxfs, ...(dxf ? [{
        sourceId,
        original,
        file: dxf
      }] : [])];
      for (const change of changes) {
        const source = [...ctx.cadFiles, ...ctx.predictionFiles].find(item => item.id === change.sourceId);
        if (!source || source.file !== change.original) throw new Error('Chỉ sửa DXF đang có trong dự án');
      }
      if (rows) {
        const name = this.csv(csvId)?.name || 'TieuChi.csv';
        const file = new File([await ctx.resultsCsvFile(rows, columns).arrayBuffer()], name, {
          type: 'text/csv;charset=utf-8'
        });
        const transfer = new DataTransfer();
        transfer.items.add(file);
        ctx.$('csv-file').files = transfer.files;
        // Scoring invalidates old predictions, including a separately imported result CSV.
        ctx.$('result-file').files = new DataTransfer().files;
        const resultLabel = document.querySelector('[data-file-label="result-file"]');
        if (resultLabel) resultLabel.textContent = 'Chưa chọn file';
        const label = document.querySelector('[data-file-label="csv-file"]');
        if (label) label.textContent = file.name;
        ++ctx.predictionTableVersion;
        ctx.renderResults([], false);
        ctx.renderPredictionTable(rows, false, rows.length, columns);
        ctx.showStatus('predict-message', 'Đã cập nhật bảng từ chatbot, có thể kiểm tra rồi chạy mô hình');
      }
      if (changes.length) {
        for (const change of changes) {
          const source = [...ctx.cadFiles, ...ctx.predictionFiles].find(item => item.id === change.sourceId);
          source.file = change.file;
          source.key = JSON.stringify([change.file.name, change.file.size, change.file.lastModified]);
          delete source.columns;
          delete source.diagnostics;
          delete source.error;
        }
        ++ctx.mapRequestVersion;
        ctx.mapRequestController?.abort();
        ctx.updateCadOptions();
        ctx.updatePredictionSources();
        await ctx.readPredictionSources();
      }
      if ((changes.length || rows) && ctx.sharedSourceCrs() && (ctx.cadFiles.length || ctx.predictionFiles.length)) {
        const version = ++ctx.mapRequestVersion;
        ctx.mapRequestController?.abort();
        ctx.mapRequestController = new AbortController();
        ctx.$('source-crs').value = ctx.sharedSourceCrs();
        const form = new FormData(ctx.$('map-form'));
        form.delete('cad');
        form.delete('layer');
        for (const item of ctx.cadFiles) {
          form.append('cad', item.file);
          form.append('cad_id', item.id);
        }
        for (const item of ctx.predictionFiles) {
          if (item.error || !item.columns) throw new Error('Không đọc được lưới đã sửa');
          form.append('layer', item.file);
          form.append('layer_id', item.id);
          form.append('layer_join', ctx.individualPredictionJoins() ? item.joinColumn : ctx.$('gpkg-join').value);
        }
        if (ctx.predictionRows.length && !ctx.$('result-file').files.length) form.set('result', ctx.resultsCsvFile(ctx.predictionRows));
        const payload = await ctx.api('/api/map', {
          method: 'POST',
          body: form,
          signal: ctx.mapRequestController.signal
        });
        if (version !== ctx.mapRequestVersion) throw new Error('Bản đồ vừa thay đổi, hãy tạo lại đề xuất');
        const center = ctx.map?.getCenter(),
          zoom = ctx.map?.getZoom();
        const styles = ctx.overlays;
        ctx.renderMap(payload.layers, styles);
        if (center) {
          ctx.pendingMapBounds = null;
          ctx.map.setView(center, zoom, {
            animate: false
          });
        }
      } else if (changes.length && ctx.overlays.length) {
        throw new Error('Chọn hệ tọa độ để hiển thị DXF đã sửa trên bản đồ');
      }
      window.workspacePersistence?.schedule();
    }
  };
  ctx.assistantHistory = new WorkspaceHistory({
    capture: () => window.workspacePersistence.checkpoint(),
    restore: snapshot => window.workspacePersistence.restoreCheckpoint(snapshot),
    pause: async () => {
      if (ctx.$('predict-button').disabled || ctx.resultColumnsLoading || ctx.predictionFiles.some(item => item.loading)) {
        throw new Error('Chờ tác vụ dữ liệu hiện tại hoàn tất trước khi xem bản nháp');
      }
      ctx.invalidateMapPreview();
      ++ctx.predictionTableVersion;
      await window.workspacePersistence.pausePreview();
    },
    resume: () => window.workspacePersistence.resumePreview(),
    changed: () => ctx.updateAssistantHistory()
  });
  ctx.historyBar = document.createElement('div');
  ctx.historyBar.className = 'assistant-history-bar';
  ctx.historyBar.innerHTML = `<span class="sr-only" role="status" aria-live="polite">Lịch sử chỉnh sửa AI</span>
    <button type="button" data-action="confirm" hidden>Xác nhận thay đổi</button>
    <button type="button" data-action="discard" hidden>Bỏ bản nháp</button>
    <button type="button" data-action="undo" aria-label="Hoàn tác" title="Hoàn tác" disabled><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M3 10a9 9 0 1 1 2 8M3 4v6h6"/></svg></button>
    <button type="button" data-action="redo" aria-label="Làm lại" title="Làm lại" disabled><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M21 10a9 9 0 1 0-2 8M21 4v6h-6"/></svg></button>`;
  document.querySelector('.workspace-header').append(ctx.historyBar);
  Object.assign(window.assistantWorkspace, {
    stage: change => ctx.assistantHistory.stage(() => window.assistantWorkspace.commit(change)),
    confirm: () => ctx.assistantHistory.confirm(),
    discard: () => ctx.assistantHistory.travel('discard'),
    hasDraft: () => !!ctx.assistantHistory.pending,
    history: () => ctx.assistantHistory.export(),
    restoreHistory: value => ctx.assistantHistory.import(value),
    travel: action => ctx.assistantHistory.travel(action),
    historyState: () => ({
      pending: !!ctx.assistantHistory.pending,
      busy: ctx.assistantHistory.busy,
      undo: ctx.assistantHistory.past.length,
      redo: ctx.assistantHistory.future.length
    })
  });
  ctx.historyBar.addEventListener('click', async event => {
    const action = event.target.closest('button')?.dataset.action;
    if (!action) return;
    try {
      if (action === 'confirm') await ctx.assistantHistory.confirm();else await ctx.assistantHistory.travel(action);
    } catch (error) {
      ctx.historyBar.querySelector('[role="status"]').textContent = error.message;
      const notice = document.querySelector('.assistant-notice');
      if (notice) notice.textContent = error.message;
    }
  });
}
