// Apply color grading to vector colors only, never the shared map canvas/tiles.
// Matrices follow W3C Filter Effects (hue-rotate, saturate, brightness, contrast, invert).
const ColorAdjustments = (() => {
    const defaults = Object.freeze({ hue: 0, saturation: 100, brightness: 100, contrast: 100, invert: 0 });
    const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

    function normalize(settings = {}) {
        return Object.fromEntries(Object.entries(defaults).map(([key, fallback]) => {
            const value = Number(settings?.[key] ?? fallback);
            const maximum = key === "hue" ? 180 : key === "invert" ? 100 : 200;
            return [key, Number.isFinite(value) ? clamp(value, key === "hue" ? -180 : 0, maximum) : fallback];
        }));
    }

    function apply(color, settings = {}) {
        const values = normalize(settings);
        if (Object.keys(defaults).every((key) => values[key] === defaults[key])) return color;
        if (typeof color !== "string" || !/^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(color)) return color;
        let hex = color.slice(1);
        if (hex.length === 3) hex = [...hex].map((digit) => digit + digit).join("");
        let rgb = [0, 2, 4].map((index) => parseInt(hex.slice(index, index + 2), 16) / 255);
        const multiply = (matrix) => matrix.map((row) => clamp(row.reduce((sum, coefficient, index) => sum + coefficient * rgb[index], 0), 0, 1));
        if (values.hue !== 0) {
            const angle = values.hue * Math.PI / 180;
            const c = Math.cos(angle), s = Math.sin(angle);
            rgb = multiply([
                [0.213 + 0.787 * c - 0.213 * s, 0.715 - 0.715 * c - 0.715 * s, 0.072 - 0.072 * c + 0.928 * s],
                [0.213 - 0.213 * c + 0.143 * s, 0.715 + 0.285 * c + 0.140 * s, 0.072 - 0.072 * c - 0.283 * s],
                [0.213 - 0.213 * c - 0.787 * s, 0.715 - 0.715 * c + 0.715 * s, 0.072 + 0.928 * c + 0.072 * s],
            ]);
        }
        if (values.saturation !== 100) {
            const s = values.saturation / 100;
            rgb = multiply([
                [0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s],
                [0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s],
                [0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s],
            ]);
        }
        rgb = rgb.map((channel) => clamp(channel * values.brightness / 100, 0, 1));
        rgb = rgb.map((channel) => clamp((channel - 0.5) * values.contrast / 100 + 0.5, 0, 1));
        const inversion = values.invert / 100;
        rgb = rgb.map((channel) => clamp(channel * (1 - 2 * inversion) + inversion, 0, 1));
        return "#" + rgb.map((channel) => Math.round(channel * 255).toString(16).padStart(2, "0")).join("");
    }

    return { defaults, normalize, apply };
})();

if (typeof module !== "undefined" && module.exports) module.exports = ColorAdjustments;
