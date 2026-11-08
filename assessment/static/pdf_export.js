/* Freeze the visible Leaflet viewport for native printing / Save as PDF.
 * Raster images stay DOM images (no cross-origin canvas readback).
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    else { root.MapPdfExport = api; api.bind(); }
})(globalThis, function () {
    "use strict";

    function fitPage(width, height) {
        if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
            throw new Error("Bản đồ chưa có kích thước hiển thị hợp lệ.");
        }
        const mmPerPixel = Math.min(281 / width, 166 / height);
        return { width: width * mmPerPixel, height: height * mmPerPixel,
            scale: mmPerPixel * 96 / 25.4 };
    }

    function intersects(first, second) {
        return first.right > second.left && first.left < second.right
            && first.bottom > second.top && first.top < second.bottom;
    }

    function missingTiles(container) {
        const viewport = container.getBoundingClientRect();
        return [...container.querySelectorAll(".leaflet-tile")].filter((tile) => {
            const image = tile.matches("img") ? tile : tile.querySelector("img");
            return image && intersects(tile.getBoundingClientRect(), viewport)
                && (!image.complete || !image.naturalWidth);
        }).length;
    }

    function cloneMap(container) {
        const clone = container.cloneNode(true);
        const originals = [...container.querySelectorAll("img")];
        const images = [...clone.querySelectorAll("img")];
        originals.forEach((image, index) => {
            // Freeze only already rendered images; do not silently fill holes later.
            if (!image.complete || !image.naturalWidth) images[index].remove();
            else { images[index].src = image.currentSrc || image.src; images[index].loading = "eager"; }
        });
        const canvases = [...clone.querySelectorAll("canvas")];
        [...container.querySelectorAll("canvas")].forEach((canvas, index) => {
            const image = document.createElement("img");
            image.src = canvas.toDataURL("image/png");
            image.alt = "Layer bản đồ";
            image.className = canvas.className;
            image.style.cssText = canvas.style.cssText;
            const computed = getComputedStyle(canvas);
            Object.assign(image.style, { position: computed.position, zIndex: computed.zIndex,
                width: computed.width, height: computed.height, maxWidth: "none", maxHeight: "none" });
            image.dataset.mapCanvas = "true";
            canvases[index].replaceWith(image);
        });
        clone.querySelectorAll(".leaflet-control-container, .leaflet-popup-pane, .leaflet-tooltip-pane").forEach((element) => element.remove());
        clone.removeAttribute("id");
        clone.removeAttribute("tabindex");
        Object.assign(clone.style, { position: "relative", inset: "auto", margin: "0", border: "0",
            width: `${container.clientWidth}px`, height: `${container.clientHeight}px`,
            overflow: "hidden", background: getComputedStyle(container).backgroundColor });
        clone.dataset.mapSnapshot = "true";
        return clone;
    }

    function imageReady(image) {
        return new Promise((resolve) => {
            if (image.complete) { resolve(image.naturalWidth > 0); return; }
            const timer = setTimeout(() => finish(false), 10000);
            const finish = (loaded) => {
                clearTimeout(timer); image.onload = image.onerror = null; resolve(loaded);
            };
            image.onload = () => finish(true);
            image.onerror = () => finish(false);
        });
    }

    async function prepare(popup, container, missing) {
        const size = fitPage(container.clientWidth, container.clientHeight);
        const snapshot = cloneMap(container);
        const doc = document.implementation.createHTMLDocument("Ban-do");
        doc.documentElement.lang = "vi";
        const charset = doc.createElement("meta"); charset.charset = "utf-8"; doc.head.append(charset);
        const style = doc.createElement("style");
        style.textContent = `
            @page { size: A4 landscape; margin: 8mm; }
            * { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            body { margin: 0; background: #e8edea; font: 12px Arial, sans-serif; color: #203a2b; }
            .paper { width: 297mm; padding: 8mm; margin: 12px auto; background: white; }
            h1 { margin: 0 0 3mm; font-size: 14pt; }
            .map-frame { width: ${size.width}mm; height: ${size.height}mm; margin: 0 auto; overflow: hidden; position: relative; }
            .snapshot-scale { width: ${container.clientWidth}px; height: ${container.clientHeight}px; transform: scale(${size.scale}); transform-origin: 0 0; }
            .map-meta, .source-credits, .map-warning { margin: 2mm 0 0; font-size: 8pt; line-height: 1.25; }
            .map-warning { color: #8b310d; }
            .preview-toolbar { padding: 10px; text-align: center; }
            .preview-toolbar button { padding: 8px 12px; margin-right: 8px; cursor: pointer; }
            .preview-toolbar p { margin: 6px 0 0; }
            @media print { body { background: white; } .preview-toolbar { display: none; } .paper { width: 281mm; padding: 0; margin: 0; } }
        `;
        doc.head.append(style);
        // Inline already loaded, same-origin rules: the preview should not
        // depend on an additional localhost stylesheet request.
        const href = document.querySelector('link[href*="leaflet/leaflet.css"]').href;
        const sheet = [...document.styleSheets].find((entry) => entry.href === href);
        let rules = "";
        try { rules = [...sheet.cssRules].map((rule) => rule.cssText).join("\n"); } catch { /* Fetch fallback below. */ }
        const cssReady = (async () => {
            if (!rules) {
                const response = await fetch(href, { signal: AbortSignal.timeout(10000) });
                if (!response.ok) throw new Error("Không tải được kiểu hiển thị bản đồ.");
                rules = await response.text();
            }
            const leaflet = doc.createElement("style"); leaflet.textContent = rules; doc.head.append(leaflet);
        })();
        const toolbar = doc.createElement("div"); toolbar.className = "preview-toolbar";
        const printButton = doc.createElement("button"); printButton.id = "print-map-now";
        printButton.textContent = "In / Lưu PDF"; printButton.disabled = true;
        const closeButton = doc.createElement("button"); closeButton.id = "close-map-preview"; closeButton.textContent = "Đóng";
        const help = doc.createElement("p");
        help.textContent = "Chọn Lưu dưới dạng PDF (Save as PDF). Khổ A4 ngang; tắt đầu/chân trang của trình duyệt nếu không cần.";
        toolbar.append(printButton, closeButton, help);
        const paper = doc.createElement("main"); paper.className = "paper";
        const title = doc.createElement("h1"); title.textContent = "Bản đồ đang hiển thị";
        const frame = doc.createElement("div"); frame.className = "map-frame";
        const scale = doc.createElement("div"); scale.className = "snapshot-scale";
        scale.append(doc.importNode(snapshot, true)); frame.append(scale);
        const meta = doc.createElement("p"); meta.className = "map-meta";
        meta.textContent = `${document.getElementById("map-basemap-status").textContent} - ${document.getElementById("map-crs-status").textContent}`;
        const credits = doc.createElement("div"); credits.className = "source-credits";
        const attribution = container.querySelector(".leaflet-control-attribution");
        if (attribution) for (const node of attribution.childNodes) credits.append(node.cloneNode(true));
        const warning = doc.createElement("p"); warning.className = "map-warning";
        if (missing) warning.textContent = "Nền bản đồ chưa tải đủ. Bản xuất chỉ gồm phần đã tải tại thời điểm chụp.";
        paper.append(title, frame, meta, credits, warning); doc.body.append(toolbar, paper);
        await cssReady;
        if (popup.closed) return;
        // A real, same-origin Blob navigation gives images a fresh active
        // document. Moving live img nodes into about:blank can leave requests
        // perpetually pending in embedded Chromium browsers.
        const blobUrl = URL.createObjectURL(new Blob(["<!doctype html>", doc.documentElement.outerHTML], { type: "text/html;charset=utf-8" }));
        await new Promise((resolve, reject) => {
            const timer = setTimeout(() => { clearInterval(poll); URL.revokeObjectURL(blobUrl); reject(new Error("Không mở được trang xem trước PDF.")); }, 10000);
            const poll = setInterval(() => {
                if (popup.closed) { clearTimeout(timer); clearInterval(poll); resolve(); return; }
                try {
                    if (popup.location.href === blobUrl && popup.document.getElementById("print-map-now")) {
                        clearTimeout(timer); clearInterval(poll); resolve();
                    }
                } catch { /* Wait until the initial blank document is replaced. */ }
            }, 40);
            popup.location.replace(blobUrl);
        });
        if (popup.closed) { URL.revokeObjectURL(blobUrl); return; }
        popup.addEventListener("pagehide", () => URL.revokeObjectURL(blobUrl), { once: true });
        const liveDoc = popup.document;
        const print = liveDoc.getElementById("print-map-now");
        print.onclick = () => { popup.focus(); popup.print(); };
        liveDoc.getElementById("close-map-preview").onclick = () => popup.close();
        const printedImages = [...liveDoc.querySelectorAll(".map-frame img")];
        const loaded = await Promise.all(printedImages.map(imageReady));
        if (popup.closed) return;
        if (printedImages.some((image, index) => image.dataset.mapCanvas && !loaded[index])) {
            throw new Error("Không đọc được ảnh layer. Thử thu nhỏ vùng bản đồ rồi xuất lại.");
        }
        if (loaded.some((value) => !value)) {
            liveDoc.querySelector(".map-warning").textContent = "Một số ảnh nền không tải được trong trang in. Kiểm tra bản xem trước trước khi lưu PDF.";
            if (!popup.confirm("Một số ảnh nền chưa tải được trong trang in. Bạn vẫn muốn tiếp tục?")) {
                print.disabled = false; liveDoc.documentElement.dataset.pdfReady = "true"; return;
            }
        }
        print.disabled = false;
        liveDoc.documentElement.dataset.pdfReady = "true";
        popup.focus(); popup.print();
    }

    function updateButton() {
        const button = document.getElementById("map-export-pdf");
        if (button) button.disabled = document.getElementById("map-panel").hidden;
    }
    function bind() {
        const button = document.getElementById("map-export-pdf");
        const message = document.getElementById("map-export-status");
        button.addEventListener("click", async () => {
            if (document.getElementById("map-panel").inert) {
                message.textContent = "Chờ khôi phục phiên làm việc trước khi xuất."; return;
            }
            const container = document.getElementById("leafletMap");
            const missing = missingTiles(container);
            if (missing && !window.confirm("Nền bản đồ chưa tải đủ hoặc đang lỗi mạng. PDF sẽ chỉ có phần đã tải và các layer hiện tại. Vẫn xuất?")) return;
            const popup = window.open("", "_blank", "width=1180,height=840");
            if (!popup) { message.textContent = "Trình duyệt chặn cửa sổ in. Cho phép cửa sổ bật lên rồi thử lại."; return; }
            message.textContent = "Đang chuẩn bị bản đồ…"; button.disabled = true;
            try {
                await prepare(popup, container, missing);
                message.textContent = "Đã mở trang in. Chọn Lưu dưới dạng PDF.";
            } catch (error) {
                message.textContent = `Không xuất được: ${error.message}`;
                if (!popup.closed) popup.document.body.textContent = `Không tạo được bản in: ${error.message}. Đóng cửa sổ này rồi thử lại.`;
            } finally { updateButton(); }
        });
        document.getElementById("map-tab").addEventListener("click", updateButton);
        document.getElementById("predict-tab").addEventListener("click", updateButton);
        updateButton();
    }
    return { fitPage, intersects, missingTiles, cloneMap, bind };
});
