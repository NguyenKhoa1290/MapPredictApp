/* Atomic browser-local snapshots. Heavy blobs/GeoJSON are rewritten only on change. */
(function (root) {
    "use strict";
    class WorkspaceStore {
        constructor(factory = root.indexedDB, name = "mapPredict.workspace") {
            this.factory = factory;
            this.name = name;
            this.revision = 0;
            this.references = new Map();
            this.assetKeys = [];
        }
        async open() {
            if (this.db) return;
            if (!this.factory) throw new Error("Browser storage unavailable");
            this.db = await new Promise((resolve, reject) => {
                const request = this.factory.open(this.name, 1);
                request.onupgradeneeded = () => {
                    request.result.createObjectStore("state");
                    request.result.createObjectStore("assets");
                };
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
                request.onblocked = () => reject(new Error("Browser storage blocked by another tab"));
            });
            this.db.onversionchange = () => { this.db.close(); this.db = null; };
        }
        async read() {
            await this.open();
            return new Promise((resolve, reject) => {
                const tx = this.db.transaction(["state", "assets"], "readonly");
                let state = null;
                const assets = new Map();
                const request = tx.objectStore("state").get("workspace");
                request.onsuccess = () => {
                    state = request.result;
                    for (const key of state?.assetKeys || []) {
                        const asset = tx.objectStore("assets").get(key);
                        asset.onsuccess = () => assets.set(key, asset.result);
                    }
                };
                tx.oncomplete = () => {
                    this.revision = state?.revision || 0;
                    this.assetKeys = state?.assetKeys || [];
                    this.references = new Map(assets);
                    resolve(state ? { state, assets } : null);
                };
                tx.onabort = () => reject(tx.error || new Error("Cannot read workspace"));
            });
        }
        // Called only by the UI's serial save queue; returns after transaction commit.
        write(state, assets) {
            return new Promise((resolve, reject) => {
                const tx = this.db.transaction(["state", "assets"], "readwrite");
                const revision = this.revision + 1;
                const savedAt = Date.now();
                const keys = [...assets.keys()];
                let failure = null;
                // A stalled browser transaction must not lock draft review forever.
                const timeout = setTimeout(() => {
                    failure = new Error('Lưu trên trình duyệt quá thời gian, hãy thử lại');
                    try { tx.abort(); } catch { /* Already completed. */ }
                }, 30000);
                const request = tx.objectStore("state").get("workspace");
                request.onsuccess = () => {
                    if ((request.result?.revision || 0) !== this.revision) {
                        failure = new Error("Workspace changed in another tab");
                        failure.name = "WorkspaceConflictError";
                        tx.abort();
                        return;
                    }
                    try {
                        const store = tx.objectStore("assets");
                        for (const key of this.assetKeys) if (!assets.has(key)) store.delete(key);
                        for (const [key, value] of assets) {
                            if (this.references.get(key) !== value) store.put(value, key);
                        }
                        tx.objectStore("state").put({ ...state, revision, savedAt, assetKeys: keys }, "workspace");
                    } catch (error) { failure = error; tx.abort(); }
                };
                tx.oncomplete = () => {
                    clearTimeout(timeout);
                    this.revision = revision;
                    this.assetKeys = keys;
                    this.references = new Map(assets);
                    resolve({ revision, savedAt });
                };
                tx.onabort = () => {
                    clearTimeout(timeout);
                    reject(failure || tx.error || new Error("Cannot save workspace"));
                };
            });
        }
    }
    root.WorkspaceStore = WorkspaceStore;
    // Bounded history, saved atomically with workspace assets in IndexedDB.
    class WorkspaceHistory {
        constructor({ capture, restore, pause, resume, changed = () => {}, limit = 10 }) {
            Object.assign(this, { capture, restore, pause, resume, changed, limit });
            this.past = []; this.future = []; this.pending = null; this.busy = false;
            this.persisted = null;
        }
        key(snapshot) {
            const { view, tab, details, inspector, basemap, labels, ...data } = snapshot.state;
            if (Array.isArray(data.layers)) data.layers = data.layers.map(({ id, sourceKey }) => ({ id, sourceKey }));
            return JSON.stringify([data, [...snapshot.assets].sort(([a], [b]) => a.localeCompare(b)).map(([key, value]) =>
                [key, key === 'table:view' ? !value?.rows?.length && !value?.columns?.length ? null
                    : { ...value, columns: value.columns || [...new Set(value.rows.flatMap(row => Object.keys(row)))] }
                    : value instanceof Blob ? [value.size, value.type] : value])]);
        }
        export() { return this.persisted ||= { version: 1, past: this.past, future: this.future, pending: this.pending }; }
        import(value) {
            if (!value) { this.changed(); return; }
            if (value.version !== 1 || !Array.isArray(value.past) || !Array.isArray(value.future)
                || value.past.length + value.future.length > this.limit
                || [...value.past, ...value.future, ...(value.pending ? [value.pending] : [])].some(item => !item?.before?.state || !item?.after?.state
                    || Object.prototype.toString.call(item.before.assets) !== '[object Map]'
                    || Object.prototype.toString.call(item.after.assets) !== '[object Map]')) {
                throw new Error('Lịch sử chỉnh sửa đã lưu không hợp lệ');
            }
            this.past = value.past; this.future = value.future; this.pending = value.pending || null;
            this.persisted = value; this.changed();
        }
        assertCurrent(snapshot) {
            if (this.key(this.capture()) !== this.key(snapshot)) {
                throw new Error('Tài nguyên đã thay đổi, không thể ghi đè bằng thao tác AI cũ');
            }
        }
        async stage(action) {
            if (this.busy || this.pending) throw new Error('Hãy xác nhận hoặc bỏ bản nháp hiện tại');
            this.busy = true; this.changed();
            let before, paused = false;
            try {
                await this.pause(); paused = true;
                before = this.capture();
                await action();
                const after = this.capture();
                this.pending = { before, after };
                this.persisted = null;
                // Save the displayed draft and its review state together before returning.
                await this.resume();
            } catch (error) {
                this.pending = null; this.persisted = null;
                if (before) await this.restore(before);
                if (paused) await this.resume();
                throw error;
            } finally { this.busy = false; this.changed(); }
        }
        async confirm() {
            if (this.busy || !this.pending) return;
            this.assertCurrent(this.pending.after);
            this.past.push(this.pending);
            if (this.past.length > this.limit) this.past.shift();
            this.future = []; this.pending = null;
            this.persisted = null;
            this.changed(); await this.resume();
        }
        async travel(direction) {
            if (this.busy) return;
            const discard = direction === 'discard';
            if (!discard && this.pending) throw new Error('Hãy xác nhận hoặc bỏ bản nháp trước');
            const from = direction === 'redo' ? this.future : this.past;
            const to = direction === 'redo' ? this.past : this.future;
            const item = discard ? this.pending : from.at(-1);
            if (!item) return;
            this.assertCurrent(direction === 'redo' ? item.before : item.after);
            this.busy = true; this.changed();
            try {
                await this.restore(direction === 'redo' ? item.after : item.before);
                if (discard) this.pending = null;
                else { from.pop(); to.push(item); }
                this.persisted = null;
                await this.resume();
            } finally { this.busy = false; this.changed(); }
        }
    }
    root.WorkspaceHistory = WorkspaceHistory;
})(globalThis);
