/* Restore files and rendered layers without rerunning predictions or map uploads. */
(() => {
    "use strict";
    const store = new WorkspaceStore();
    const fileInputs = ["csv-file", "result-file"];
    let ready = false;
    let blocked = false;
    let dirty = false;
    let timer = null;
    let saving = null;
    let restoredResults = false;
    let previewPaused = false;

    function status(text, error = false) {
        $("workspace-save-status").textContent = text;
        $("workspace-save-status").classList.toggle("text-danger", error);
        $("workspace-save-status").parentElement.classList.toggle("has-error", error);
    }
    function fileValue(file) {
        return file ? { name: file.name, type: file.type, lastModified: file.lastModified } : null;
    }
    function capture() {
        const assets = new Map();
        const sources = (entries, kind) => entries.map((entry) => {
            const assetKey = `file:${entry.id}`;
            assets.set(assetKey, entry.file);
            const card = kind === "cad" ? cadAnalysisCards.find((state) => state.entry === entry)?.card : null;
            return {
                id: entry.id, key: entry.key, assetKey, file: fileValue(entry.file),
                offsetX: card?.querySelector('[name="cad_offset_x"]').value ?? entry.offsetX ?? "0",
                offsetY: card?.querySelector('[name="cad_offset_y"]').value ?? entry.offsetY ?? "0",
                columns: entry.columns, diagnostics: entry.diagnostics,
                suggestedJoin: entry.suggestedJoin, joinColumn: entry.joinColumn, error: entry.error,
            };
        });
        const cad = sources(cadFiles, "cad");
        const prediction = sources(predictionFiles, "prediction");
        const inputs = {};
        for (const id of fileInputs) {
            const file = $(id).files[0];
            if (file) { inputs[id] = fileValue(file); assets.set(`input:${id}`, file); }
        }
        const layers = overlays.map((overlay) => {
            assets.set(`layer:${overlay.id}`, overlay.item);
            return {
                id: overlay.id, color: overlay.color, opacity: overlay.opacity, visible: overlay.visible,
                style: { ...overlay.style }, adjustments: { ...overlay.adjustments },
                groups: [...overlay.groups].map(([key, group]) => [key, {
                    visible: group.visible, style: { ...group.style },
                }]),
            };
        });
        assets.set("table:results", predictionRows);
        assets.set("table:view", predictionView);
        const center = map?.getCenter();
        return { assets, state: {
            schema: 1, cad, prediction, inputs, layers,
            crs: sharedSourceCrs(), mapCrs: $("map-crs-status").textContent,
            tab: $("map-panel").hidden ? "predict-tab" : "map-tab",
            view: center ? { center: [center.lat, center.lng], zoom: map.getZoom() } : null,
            basemap: activeBasemap, labels: $("basemap-labels").checked,
            joins: { layer: $("gpkg-join").value, csv: $("csv-join").value, mode: $("join-mode").value,
                csvColumns: [...$("csv-join").options].map((option) => option.value) },
            offsetX: $("prediction-offset-x").value, offsetY: $("prediction-offset-y").value,
            inspector: { selectedLayerId, scope: inspectorScope,
                componentSearch: $("component-search").value, attributeSearch: $("attribute-search").value,
                componentPage, attributePage },
            details: [...document.querySelectorAll("details")].map((element) => element.open),
        } };
    }
    function schedule() {
        if (!ready || blocked || previewPaused) return;
        dirty = true;
        status("Đang chờ tự lưu…");
        clearTimeout(timer);
        timer = setTimeout(flush, 180);
    }
    function flush() {
        clearTimeout(timer);
        if (!ready || blocked || previewPaused) return Promise.resolve(false);
        if (saving) return saving;
        // Start the transaction synchronously when the page is being hidden.
        saving = (async () => {
            try {
                while (dirty) {
                    dirty = false;
                    status("Đang tự lưu trên trình duyệt…");
                    const snapshot = capture();
                    await store.write(snapshot.state, snapshot.assets);
                }
                status("Đã tự lưu trên trình duyệt");
                return true;
            } catch (error) {
                dirty = true;
                if (error.name === "WorkspaceConflictError") {
                    blocked = true;
                    status("Tab khác đã lưu phiên mới. Tải lại trang trước khi lưu tiếp.", true);
                } else {
                    status(error.name === "QuotaExceededError"
                        ? "Không đủ dung lượng lưu. Chưa lưu được thay đổi mới."
                        : "Chưa tự lưu được. Giữ trang mở; ứng dụng sẽ thử lại khi bạn thao tác.", true);
                }
                return false;
            } finally { saving = null; }
        })();
        return saving;
    }
    function restoreFile(value, metadata) {
        if (!(value instanceof Blob)) throw new Error("Saved file is missing");
        return new File([value], metadata.name, { type: metadata.type, lastModified: metadata.lastModified });
    }
    function restore(snapshot) {
        const { state, assets } = snapshot;
        if (state.schema !== 1 || !Array.isArray(state.layers) || !Array.isArray(state.cad)
            || !Array.isArray(state.prediction)) throw new Error("Unsupported workspace snapshot");
        // Validate essential assets before mutating the displayed workspace.
        for (const source of [...state.cad, ...state.prediction]) {
            if (!(assets.get(source.assetKey) instanceof Blob)) throw new Error("Saved source missing");
        }
        for (const layer of state.layers) {
            if (!Array.isArray(assets.get(`layer:${layer.id}`)?.data?.features)) throw new Error("Saved layer missing");
        }
        for (const [id] of Object.entries(state.inputs)) {
            if (!fileInputs.includes(id)) continue;
            if (!(assets.get(`input:${id}`) instanceof Blob)) throw new Error("Saved input missing");
        }
        const sources = (entries) => entries.map((entry) => ({ ...entry,
            file: restoreFile(assets.get(entry.assetKey), entry.file), loading: false,
        }));
        cadFiles = sources(state.cad);
        predictionFiles = sources(state.prediction);
        for (const id of fileInputs) {
            const metadata = state.inputs[id];
            const transfer = new DataTransfer();
            if (metadata) transfer.items.add(restoreFile(assets.get(`input:${id}`), metadata));
            $(id).files = transfer.files;
            const label = document.querySelector(`[data-file-label="${id}"]`);
            if (label) label.textContent = metadata?.name || label.dataset.defaultLabel || 'Chưa chọn file';
        }
        const crs = state.crs || "";
        const listed = [...$("project-crs").options].some((option) => option.value === crs);
        $("project-crs").value = listed ? crs : "custom";
        $("project-crs-custom").value = listed ? "" : crs;
        applySharedCrs(false);
        updateCadOptions();
        gpkgJoinPreference = state.joins.layer;
        updatePredictionSources();
        predictionRows = assets.get("table:results") || [];
        restoredResults = predictionRows.length > 0;
        renderResults(predictionRows, false);
        const view = assets.get("table:view");
        if (view) renderPredictionTable(view.rows, view.isResult, view.total);
        else renderPredictionTable([], false);
        fillSelect($("csv-join"), state.joins.csvColumns);
        $("csv-join").value = state.joins.csv;
        $("join-mode").value = state.joins.mode === "numeric" ? "numeric" : "exact";
        if ([...$("gpkg-join").options].some((option) => option.value === state.joins.layer)) $("gpkg-join").value = state.joins.layer;
        $("prediction-offset-x").value = state.offsetX;
        $("prediction-offset-y").value = state.offsetY;
        // Seed lightweight styles before rebuilding Leaflet paths from cached data.
        const savedLayers = state.layers.map((layer) => ({ ...layer, groups: new Map(layer.groups) }));
        renderMap(state.layers.map((layer) => assets.get(`layer:${layer.id}`)), savedLayers);
        const inspector = state.inspector;
        if (inspector?.selectedLayerId && overlays.some((overlay) => overlay.id === inspector.selectedLayerId)) {
            selectManagedLayer(inspector.selectedLayerId, inspector.scope);
            $("component-search").value = inspector.componentSearch;
            $("attribute-search").value = inspector.attributeSearch;
            componentPage = inspector.componentPage; attributePage = inspector.attributePage;
            renderComponents(currentOverlay()); renderAttributes(currentOverlay());
        }
        $("basemap-labels").checked = state.labels;
        selectBasemap(state.basemap);
        $(state.tab === "predict-tab" ? "predict-tab" : "map-tab").click();
        pendingMapBounds = null;
        if (state.view) {
            map.stop(); map.invalidateSize({ pan: false });
            map.setView(state.view.center, state.view.zoom, { animate: false });
        }
        $("map-crs-status").textContent = state.mapCrs;
        [...document.querySelectorAll("details")].forEach((element, index) => { element.open = !!state.details[index]; });
        showStatus("map-message", `Đã khôi phục ${overlays.length} layer từ bản lưu trên trình duyệt.`);
    }
    async function boot() {
        const surfaces = [...document.querySelectorAll(".workspace-panel, .workspace-header > :not(.workspace-save)")];
        surfaces.forEach((element) => { element.inert = true; });
        try {
            const snapshot = await store.read();
            if (snapshot) {
                restore(snapshot);
                status("Đã khôi phục phiên tự lưu");
            } else {
                status("Tự động lưu thao tác trên trình duyệt");
            }
            // Drain synthetic click/toggle/resize events produced by restoration.
            // Merely opening another tab must not create a new saved revision.
            await new Promise((resolve) => setTimeout(resolve, 0));
            ready = true;
        } catch (error) {
            // Never replace an unreadable saved workspace with the initial empty UI.
            blocked = true;
            status("Không mở được bản lưu. Phiên cũ không bị ghi đè; kiểm tra quyền lưu trữ rồi tải lại.", true);
        } finally {
            surfaces.forEach((element) => { element.inert = false; });
        }
        if (ready && predictionFiles.some((entry) => !entry.columns)) await readPredictionSources();
    }
    window.workspacePersistence = { schedule, flush,
        checkpoint() {
            if (!ready || blocked) throw new Error('Phiên làm việc chưa sẵn sàng');
            return structuredClone(capture());
        },
        async pausePreview() {
            if (!ready || blocked || !await flush()) throw new Error('Chưa lưu được dữ liệu trước khi xem bản nháp');
            previewPaused = true;
        },
        resumePreview() { previewPaused = false; schedule(); },
        restoreCheckpoint(snapshot) {
            // Undo data without moving the user's viewport or changing the active tab.
            const current = capture().state;
            ++predictionTableVersion;
            ++resultColumnsVersion;
            invalidateMapPreview();
            const copy = structuredClone(snapshot);
            restore({ assets: copy.assets, state: { ...copy.state,
                view: current.view, tab: current.tab, details: current.details,
                basemap: current.basemap, labels: current.labels } });
        },
        get ready() { return ready; }, get restoredResults() { return restoredResults; } };
    for (const event of ["input", "change", "click"]) document.addEventListener(event, schedule);
    document.addEventListener("toggle", schedule, true);
    map?.on("moveend zoomend", schedule);
    window.addEventListener("pagehide", () => { void flush(); });
    document.addEventListener("visibilitychange", () => { if (document.hidden) void flush(); });
    void boot();
})();
