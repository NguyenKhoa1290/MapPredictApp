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
                    this.revision = revision;
                    this.assetKeys = keys;
                    this.references = new Map(assets);
                    resolve({ revision, savedAt });
                };
                tx.onabort = () => reject(failure || tx.error || new Error("Cannot save workspace"));
            });
        }
    }
    root.WorkspaceStore = WorkspaceStore;
})(globalThis);
