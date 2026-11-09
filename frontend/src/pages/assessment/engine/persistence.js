// DOM controller owned by the React assessment page.
export function installPersistence(ctx) {
  const {
    window,
    document,
    WorkspaceStore,
    setTimeout,
    clearTimeout
  } = ctx;
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
      if (ctx.disposed) return;
      ctx.$("workspace-save-status").textContent = text;
      ctx.$("workspace-save-status").classList.toggle("text-danger", error);
      ctx.$("workspace-save-status").parentElement.classList.toggle("has-error", error);
    }
    function fileValue(file) {
      return file ? {
        name: file.name,
        type: file.type,
        lastModified: file.lastModified
      } : null;
    }
    function capture(includeHistory = true) {
      const assets = new Map();
      const sources = (entries, kind) => entries.map(entry => {
        const assetKey = `file:${entry.id}`;
        assets.set(assetKey, entry.file);
        const card = kind === "cad" ? ctx.cadAnalysisCards.find(state => state.entry === entry)?.card : null;
        return {
          id: entry.id,
          key: entry.key,
          assetKey,
          file: fileValue(entry.file),
          offsetX: card?.querySelector('[name="cad_offset_x"]').value ?? entry.offsetX ?? "0",
          offsetY: card?.querySelector('[name="cad_offset_y"]').value ?? entry.offsetY ?? "0",
          columns: entry.columns,
          diagnostics: entry.diagnostics,
          suggestedJoin: entry.suggestedJoin,
          joinColumn: entry.joinColumn,
          error: entry.error
        };
      });
      const cad = sources(ctx.cadFiles, "cad");
      const prediction = sources(ctx.predictionFiles, "prediction");
      const inputs = {};
      for (const id of fileInputs) {
        const file = ctx.$(id).files[0];
        if (file) {
          inputs[id] = fileValue(file);
          assets.set(`input:${id}`, file);
        }
      }
      const layers = ctx.overlays.map(overlay => {
        assets.set(`layer:${overlay.id}`, overlay.item);
        return {
          id: overlay.id,
          sourceKey: overlay.sourceKey,
          color: overlay.color,
          opacity: overlay.opacity,
          visible: overlay.visible,
          predictionFillVersion: overlay.predictionFillVersion,
          style: {
            ...overlay.style
          },
          adjustments: {
            ...overlay.adjustments
          },
          groups: [...overlay.groups].map(([key, group]) => [key, {
            visible: group.visible,
            style: {
              ...group.style
            }
          }])
        };
      });
      assets.set("table:results", ctx.predictionRows);
      assets.set("table:view", ctx.predictionView);
      if (includeHistory) assets.set('history:assistant', window.assistantWorkspace.history());
      const center = ctx.map?.getCenter();
      return {
        assets,
        state: {
          schema: 1,
          cad,
          prediction,
          inputs,
          layers,
          crs: ctx.sharedSourceCrs(),
          mapCrs: ctx.$("map-crs-status").textContent,
          tab: ctx.$("map-panel").hidden ? "predict-tab" : "map-tab",
          view: center ? {
            center: [center.lat, center.lng],
            zoom: ctx.map.getZoom()
          } : null,
          basemap: ctx.activeBasemap,
          labels: ctx.$("basemap-labels").checked,
          joins: {
            layer: ctx.$("gpkg-join").value,
            csv: ctx.$("csv-join").value,
            mode: ctx.$("join-mode").value,
            csvColumns: [...ctx.$("csv-join").options].map(option => option.value)
          },
          offsetX: ctx.$("prediction-offset-x").value,
          offsetY: ctx.$("prediction-offset-y").value,
          inspector: {
            selectedLayerId: ctx.selectedLayerId,
            scope: ctx.inspectorScope,
            componentSearch: ctx.$("component-search").value,
            attributeSearch: ctx.$("attribute-search").value,
            componentPage: ctx.componentPage,
            attributePage: ctx.attributePage
          },
          details: [...document.querySelectorAll("details")].map(element => element.open)
        }
      };
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
      // A clean flush must not leave a resolved promise blocking every later save.
      if (!dirty) return Promise.resolve(true);
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
            status(error.name === "QuotaExceededError" ? "Không đủ dung lượng lưu. Chưa lưu được thay đổi mới." : "Chưa tự lưu được. Giữ trang mở; ứng dụng sẽ thử lại khi bạn thao tác.", true);
          }
          return false;
        } finally {
          saving = null;
        }
      })();
      return saving;
    }
    function restoreFile(value, metadata) {
      if (!(value instanceof Blob)) throw new Error("Saved file is missing");
      return new File([value], metadata.name, {
        type: metadata.type,
        lastModified: metadata.lastModified
      });
    }
    function restore(snapshot) {
      const {
        state,
        assets
      } = snapshot;
      if (state.schema !== 1 || !Array.isArray(state.layers) || !Array.isArray(state.cad) || !Array.isArray(state.prediction)) throw new Error("Unsupported workspace snapshot");
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
      const sources = entries => entries.map(entry => ({
        ...entry,
        file: restoreFile(assets.get(entry.assetKey), entry.file),
        loading: false
      }));
      ctx.cadFiles = sources(state.cad);
      ctx.predictionFiles = sources(state.prediction);
      for (const id of fileInputs) {
        const metadata = state.inputs[id];
        const transfer = new DataTransfer();
        if (metadata) transfer.items.add(restoreFile(assets.get(`input:${id}`), metadata));
        ctx.$(id).files = transfer.files;
        const label = document.querySelector(`[data-file-label="${id}"]`);
        if (label) label.textContent = metadata?.name || label.dataset.defaultLabel || 'Chưa chọn file';
      }
      const crs = state.crs || "";
      const listed = [...ctx.$("project-crs").options].some(option => option.value === crs);
      ctx.$("project-crs").value = listed ? crs : "custom";
      ctx.$("project-crs-custom").value = listed ? "" : crs;
      ctx.applySharedCrs(false);
      ctx.updateCadOptions();
      ctx.gpkgJoinPreference = state.joins.layer;
      ctx.updatePredictionSources();
      ctx.predictionRows = assets.get("table:results") || [];
      restoredResults = ctx.predictionRows.length > 0;
      ctx.renderResults(ctx.predictionRows, false);
      const view = assets.get("table:view");
      if (view) ctx.renderPredictionTable(view.rows, view.isResult, view.total, view.columns, view.page);else ctx.renderPredictionTable([], false);
      ctx.fillSelect(ctx.$("csv-join"), state.joins.csvColumns);
      ctx.$("csv-join").value = state.joins.csv;
      ctx.$("join-mode").value = state.joins.mode === "numeric" ? "numeric" : "exact";
      if ([...ctx.$("gpkg-join").options].some(option => option.value === state.joins.layer)) ctx.$("gpkg-join").value = state.joins.layer;
      ctx.$("prediction-offset-x").value = state.offsetX;
      ctx.$("prediction-offset-y").value = state.offsetY;
      // Seed lightweight styles before rebuilding Leaflet paths from cached data.
      const savedLayers = state.layers.map(layer => ({
        ...layer,
        groups: new Map(layer.groups)
      }));
      ctx.renderMap(state.layers.map(layer => assets.get(`layer:${layer.id}`)), savedLayers, true);
      const inspector = state.inspector;
      if (inspector?.selectedLayerId && ctx.overlays.some(overlay => overlay.id === inspector.selectedLayerId)) {
        ctx.selectManagedLayer(inspector.selectedLayerId, inspector.scope);
        ctx.$("component-search").value = inspector.componentSearch;
        ctx.$("attribute-search").value = inspector.attributeSearch;
        ctx.componentPage = inspector.componentPage;
        ctx.attributePage = inspector.attributePage;
        ctx.renderComponents(ctx.currentOverlay());
        ctx.renderAttributes(ctx.currentOverlay());
      }
      ctx.$("basemap-labels").checked = state.labels;
      ctx.selectBasemap(state.basemap);
      ctx.$(state.tab === "predict-tab" ? "predict-tab" : "map-tab").click();
      ctx.pendingMapBounds = null;
      if (state.view) {
        ctx.map.stop();
        ctx.map.invalidateSize({
          pan: false
        });
        ctx.map.setView(state.view.center, state.view.zoom, {
          animate: false
        });
      }
      ctx.$("map-crs-status").textContent = state.mapCrs;
      [...document.querySelectorAll("details")].forEach((element, index) => {
        element.open = !!state.details[index];
      });
      ctx.showStatus("map-message", `Đã khôi phục ${ctx.overlays.length} layer từ bản lưu trên trình duyệt.`);
    }
    async function boot() {
      const surfaces = [...document.querySelectorAll(".workspace-panel, .workspace-header > :not(.workspace-save)")];
      surfaces.forEach(element => {
        element.inert = true;
      });
      try {
        const snapshot = await store.read();
        if (ctx.disposed) {
          store.db?.close();
          return;
        }
        if (snapshot) {
          restore(snapshot);
          status("Đã khôi phục phiên tự lưu");
        } else {
          status("Tự động lưu thao tác trên trình duyệt");
        }
        // Drain synthetic click/toggle/resize events produced by restoration.
        // Merely opening another tab must not create a new saved revision.
        await new Promise(resolve => setTimeout(resolve, 0));
        ready = true;
        window.assistantWorkspace.restoreHistory(snapshot?.assets.get('history:assistant'));
      } catch (error) {
        // Never replace an unreadable saved workspace with the initial empty UI.
        blocked = true;
        ready = false;
        status("Không mở được bản lưu. Phiên cũ không bị ghi đè; kiểm tra quyền lưu trữ rồi tải lại.", true);
      } finally {
        surfaces.forEach(element => {
          element.inert = false;
        });
      }
      if (ready && ctx.predictionFiles.some(entry => !entry.columns)) await ctx.readPredictionSources();
      // Older saved input previews contained only the first 200 rows.
      const oldView = ctx.predictionView;
      const inputFile = ctx.$("csv-file").files[0];
      if (ready && oldView && !oldView.isResult && oldView.rows.length < oldView.total && inputFile) {
        const version = ctx.predictionTableVersion;
        try {
          const form = new FormData();
          form.append("csv", inputFile);
          const payload = await ctx.api("/api/preview-csv", {
            method: "POST",
            body: form
          });
          if (payload.rows.length !== payload.count) throw new Error("Incomplete preview");
          if (version === ctx.predictionTableVersion && ctx.predictionView === oldView && ctx.$("csv-file").files[0] === inputFile) {
            ctx.renderPredictionTable(payload.rows, false, payload.count, undefined, oldView.page);
          }
        } catch {
          if (version === ctx.predictionTableVersion && ctx.predictionView === oldView && ctx.$("csv-file").files[0] === inputFile) {
            ctx.showStatus("predict-message", "Chưa tải được đầy đủ bảng đã lưu, hãy nạp lại CSV", true);
          }
        }
      }
    }
    window.workspacePersistence = {
      schedule,
      flush,
      checkpoint() {
        if (!ready || blocked) throw new Error('Phiên làm việc chưa sẵn sàng');
        return structuredClone(capture(false));
      },
      async pausePreview() {
        if (!ready || blocked || !(await flush())) throw new Error('Chưa lưu được dữ liệu trước khi xem bản nháp');
        previewPaused = true;
      },
      async resumePreview() {
        previewPaused = false;
        schedule();
        if (!(await flush())) throw new Error('Chưa lưu được thay đổi, hãy giữ trang mở và thử lại');
      },
      restoreCheckpoint(snapshot) {
        // Undo data without moving the user's viewport or changing the active tab.
        const current = capture().state;
        ++ctx.predictionTableVersion;
        ++ctx.resultColumnsVersion;
        ctx.invalidateMapPreview();
        const copy = structuredClone(snapshot);
        restore({
          assets: copy.assets,
          state: {
            ...copy.state,
            view: current.view,
            tab: current.tab,
            details: current.details,
            basemap: current.basemap,
            labels: current.labels
          }
        });
      },
      close() {
        clearTimeout(timer);
        store.db?.close();
      },
      get ready() {
        return ready;
      },
      get restoredResults() {
        return restoredResults;
      }
    };
    for (const event of ["input", "change", "click"]) document.addEventListener(event, schedule);
    document.addEventListener("toggle", schedule, true);
    ctx.map?.on("moveend zoomend", schedule);
    window.addEventListener("pagehide", () => {
      void flush();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) void flush();
    });
    void boot();
  })();
}
