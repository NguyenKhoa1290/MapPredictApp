(function (root) {
    "use strict";
    const descriptions = {
        matched: "Khớp phần số", unmatched: "Chưa khớp", missing_key: "Thiếu mã ô",
        ambiguous: "Mã trùng hoặc mơ hồ", no_data: "Chưa có dữ liệu", invalid_y: "Y không hợp lệ",
    };
    function create({ container, button, apply }) {
        let pending = null;
        function invalidate() {
            pending = null;
            container.replaceChildren();
            container.hidden = true;
            button.hidden = true;
        }
        function show(payload) {
            invalidate();
            pending = payload;
            const document = container.ownerDocument;
            for (const layer of payload.layers) {
                const summary = layer.data.join_summary;
                if (!summary?.results_applied) continue;
                const heading = document.createElement("h3");
                heading.textContent = layer.name;
                const text = document.createElement("p");
                text.textContent = `${summary.matched}/${summary.total} ô khớp gồm ${summary.exact} chính xác và ${summary.numeric} theo phần số`;
                const issues = document.createElement("p");
                issues.textContent = `${summary.unmatched} ô chưa tô màu, ${summary.ambiguous} ô có mã mơ hồ, ${summary.no_data} ô thiếu Y, ${summary.invalid_y} ô có Y không hợp lệ, ${summary.unused_results} dòng kết quả chưa dùng`;
                container.append(heading, text, issues);
                if (summary.samples?.length) {
                    const details = document.createElement("details");
                    const title = document.createElement("summary");
                    title.textContent = "Mẫu đối chiếu mã ô và kết quả";
                    const list = document.createElement("ul");
                    for (const sample of summary.samples) {
                        const item = document.createElement("li");
                        item.textContent = `${String(sample.layer_key ?? "Thiếu mã").slice(0, 120)} → ${String(sample.result_key ?? "Không có mã đối chiếu").slice(0, 120)} · ${descriptions[sample.status] || sample.status}`;
                        list.append(item);
                    }
                    details.append(title, list);
                    container.append(details);
                }
            }
            const note = document.createElement("p");
            note.textContent = "Kiểm tra các cột và mẫu ghép trước khi áp dụng, ô chưa có dữ liệu chỉ hiện đường lưới";
            container.append(note);
            container.hidden = false;
            button.hidden = false;
        }
        button.addEventListener("click", () => {
            if (!pending) return;
            const payload = pending;
            apply(payload);
            invalidate();
        });
        return { invalidate, show };
    }
    root.JoinPreview = { create };
    if (typeof module !== "undefined") module.exports = { create };
})(typeof window !== "undefined" ? window : globalThis);
