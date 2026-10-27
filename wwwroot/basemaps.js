/* Raster overzoom and parent-tile fallback; user vector layers are independent. */
(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    else root.Basemaps = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    const MAX_ZOOM = 22;

    function motionOptions(reducedMotion = null) {
        const reduced = reducedMotion ?? (typeof globalThis.matchMedia === "function"
            && globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches);
        return {
            zoomAnimation: !reduced, fadeAnimation: !reduced, markerZoomAnimation: !reduced,
            zoomSnap: 0, zoomDelta: 0.5,
            wheelDebounceTime: 40, wheelPxPerZoomLevel: 120,
        };
    }

    function tileRequest(template, coords, depth = 0, size = 256) {
        const scale = 2 ** depth;
        const x = Math.floor(coords.x / scale);
        const y = Math.floor(coords.y / scale);
        return {
            url: template.replace("{z}", coords.z - depth).replace("{x}", x).replace("{y}", y),
            size: size * scale,
            left: -(coords.x - x * scale) * size,
            top: -(coords.y - y * scale) * size,
        };
    }

    function createFallbackLayer(L, url, options = {}) {
        // GridLayer supports arbitrary tile elements. Crop the matching quadrant
        // of a parent image, rather than repeating a complete parent in every tile.
        const FallbackLayer = L.GridLayer.extend({
            createTile(coords, done) {
                const tile = document.createElement("div");
                tile.style.overflow = "hidden";
                const image = document.createElement("img");
                image.alt = "";
                image.draggable = false;
                image.className = "basemap-tile-image";
                tile.append(image);
                // Keep geographic cropping correct with or without CSS 3D.
                // Fractional zoom is handled by the shared Leaflet map transform.
                let depth = Math.max(0, coords.z - this.options.nativeMaxZoom);
                let cancelled = false;
                const maxDepth = Math.min(coords.z, depth + this.options.fallbackDepth);
                const load = () => {
                    const request = tileRequest(url, coords, depth, this.getTileSize().x);
                    Object.assign(image.style, {
                        position: "absolute", maxWidth: "none", maxHeight: "none",
                        width: `${request.size}px`, height: `${request.size}px`,
                        left: `${request.left}px`, top: `${request.top}px`,
                    });
                    image.src = request.url;
                };
                image.onload = () => {
                    if (cancelled) return;
                    if (depth) this.fire("tilefallback", { coords, depth });
                    done(null, tile);
                };
                image.onerror = () => {
                    if (cancelled) return;
                    if (depth < maxDepth) { depth += 1; load(); }
                    else done(new Error("Basemap tile unavailable"), tile);
                };
                // Removed tiles must not keep retrying after a pan/source switch.
                tile.cancelBasemapLoad = () => {
                    cancelled = true;
                    image.onload = image.onerror = null;
                    image.removeAttribute("src");
                };
                load();
                return tile;
            },
        });
        const layer = new FallbackLayer({
            minZoom: 0, maxZoom: MAX_ZOOM, nativeMaxZoom: 19,
            fallbackDepth: 4, keepBuffer: 2, updateWhenZooming: false, updateInterval: 120, ...options,
        });
        layer.on("tileunload", ({ tile }) => tile.cancelBasemapLoad?.());
        return layer;
    }

    return { MAX_ZOOM, motionOptions, tileRequest, createFallbackLayer };
});
