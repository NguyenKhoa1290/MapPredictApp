import { useEffect, useRef, useState } from 'react';
import { getModelStatus, importResultCSV, previewPredictionCSV, runPrediction } from '../../shared/api/client';
import type { Dataset, ModelStatus } from '../../shared/api/types';
import { PlanIllustration } from '../../shared/ui/PlanIllustration';
import { useAssessmentSession } from './useAssessmentSession';

export function predictionCSV(dataset: Dataset): string {
  const quote = (value: string | number | undefined) => '"' + String(value ?? '').replaceAll('"', '""') + '"';
  return '\ufeff' + [dataset.columns.map(quote).join(','), ...dataset.rows.map(row => dataset.columns.map(column => quote(row[column])).join(','))].join('\r\n');
}

export function PredictionWorkspace({ legacyAvailable }: { legacyAvailable: boolean }) {
  const { state, setState, ready, saveStatus, saveError } = useAssessmentSession();
  const { inputFile: file, preview, resultFile, result, tab, view, page } = state;
  const dataset = view === 'result' ? result : preview;
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [modelError, setModelError] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<'preview' | 'predict' | 'import' | null>(null);
  const [modelAttempt, setModelAttempt] = useState(0);
  const request = useRef<AbortController | null>(null);
  const inputElement = useRef<HTMLInputElement>(null), resultElement = useRef<HTMLInputElement>(null);
  const mapTab = useRef<HTMLButtonElement>(null), dataTab = useRef<HTMLButtonElement>(null);
  const setTab = (value: 'map' | 'data') => setState(current => ({ ...current, tab: value }));
  useEffect(() => {
    const controller = new AbortController(); setModelError(''); setModel(null);
    getModelStatus(controller.signal).then(status => { if (!controller.signal.aborted) setModel(status); })
      .catch(reason => { if (!controller.signal.aborted) setModelError(reason instanceof Error ? reason.message : 'Chưa tải được thông tin mô hình'); });
    return () => controller.abort();
  }, [modelAttempt]);
  useEffect(() => () => request.current?.abort(), []);

  async function selectFile(next: File | null, kind: 'input' | 'result') {
    if (!next || !ready) return;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setBusy(kind === 'input' ? 'preview' : 'import'); setError('');
    try {
      if (kind === 'input') {
        const data = await previewPredictionCSV(next, controller.signal);
        if (!controller.signal.aborted) {
          if (resultElement.current) resultElement.current.value = '';
          setState(current => ({ ...current, inputFile: next, preview: data,
            resultFile: null, result: null, view: 'input', tab: 'data', page: 0 }));
        }
      } else {
        const data = await importResultCSV(next, controller.signal);
        if (!controller.signal.aborted) setState(current => ({ ...current, resultFile: next, result: data,
          view: 'result', tab: 'data', page: 0 }));
      }
    } catch (reason) {
      if (!controller.signal.aborted) {
        setError(reason instanceof Error ? reason.message : 'Chưa đọc được CSV');
        const element = kind === 'input' ? inputElement : resultElement;
        if (element.current) element.current.value = '';
      }
    } finally { if (!controller.signal.aborted) { setBusy(null); request.current = null; } }
  }

  async function predict() {
    if (!ready || !file || !preview || busy || !model?.ready) return;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller; setBusy('predict'); setError('');
    setState(current => ({ ...current, tab: 'data' }));
    try {
      const output = await runPrediction(file, controller.signal);
      if (!controller.signal.aborted) {
        if (resultElement.current) resultElement.current.value = '';
        setState(current => ({ ...current, result: { ...output, source: 'prediction' },
          resultFile: null, view: 'result', page: 0 }));
      }
    } catch (reason) { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Chưa chạy được dự đoán'); }
    finally { if (!controller.signal.aborted) { setBusy(null); request.current = null; } }
  }

  function remove(kind: 'input' | 'result') {
    request.current?.abort(); request.current = null; setBusy(null); setError('');
    if (kind === 'input') {
      if (inputElement.current) inputElement.current.value = '';
      setState(current => ({ ...current, inputFile: null, preview: null, page: 0,
        result: current.result?.source === 'uploaded' ? current.result : null,
        resultFile: current.result?.source === 'uploaded' ? current.resultFile : null,
        view: current.result?.source === 'uploaded' ? 'result' : 'input' }));
    } else {
      if (resultElement.current) resultElement.current.value = '';
      setState(current => ({ ...current, result: null, resultFile: null, view: 'input', page: 0 }));
    }
  }

  function download() {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([predictionCSV(result)], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'KetQua.csv';
    document.body.append(anchor); anchor.click(); anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const visibleRows = dataset?.rows.slice(page * 50, (page + 1) * 50) || [];
  const pages = Math.max(1, Math.ceil((dataset?.rows.length || 0) / 50));
  return <div className="assessment-shell assessment-live" aria-busy={!ready}>
    <aside className="assessment-controls" aria-label="Bảng điều khiển">
      <p className="eyebrow">Dữ liệu đánh giá</p><h2>Dữ liệu của bạn</h2>
      <p className={'assessment-save-status' + (saveError ? ' assessment-error' : '')} role="status" aria-label="Trạng thái tự lưu">{saveStatus}</p>
      <form onSubmit={event => { event.preventDefault(); void predict(); }}>
        <label className="assessment-file-label" htmlFor="assessment-csv">File dữ liệu CSV</label>
        <input id="assessment-csv" ref={inputElement} type="file" accept=".csv" disabled={!ready} onChange={event => { void selectFile(event.target.files?.[0] || null, 'input'); }} />
        {file ? <div className="assessment-file-summary"><span>Đang dùng {file.name}</span><button type="button" onClick={() => remove('input')}>Gỡ dữ liệu đầu vào</button></div> : null}
        <p className="assessment-help">Dùng các cột x1 đến x9, giá trị trống hoặc cột thiếu được tính là 0 theo cách xử lý hiện tại</p>
        <section className="assessment-model" aria-labelledby="assessment-model-title"><h3 id="assessment-model-title">Mô hình trên máy chủ</h3>
          <p>{modelError || model?.message || 'Đang kiểm tra bộ mô hình'}</p>
          {model?.model_version ? <small>Phiên bản {model.model_version}</small> : null}
          {modelError || model?.ready === false ? <button type="button" className="text-link" onClick={() => setModelAttempt(value => value + 1)}>Kiểm tra lại mô hình</button> : null}
        </section>
        <button type="submit" className="button primary" disabled={!ready || !file || !preview || Boolean(busy) || !model?.ready}>{busy === 'predict' ? 'Đang dự đoán' : 'Chạy dự đoán'}</button>
      </form>
      <section className="assessment-result-import" aria-label="Nạp kết quả có sẵn">
        <label className="assessment-file-label" htmlFor="assessment-result-csv">CSV kết quả có sẵn</label>
        <input id="assessment-result-csv" ref={resultElement} type="file" accept=".csv" disabled={!ready} onChange={event => { void selectFile(event.target.files?.[0] || null, 'result'); }} />
        <p className="assessment-help">Nạp CSV có cột Y để dùng kết quả của bạn, ô Y trống được giữ là Chưa có dữ liệu</p>
        {result ? <div className="assessment-file-summary"><span>{resultFile ? 'Đang dùng ' + resultFile.name : 'Kết quả vừa dự đoán'}</span><button type="button" onClick={() => remove('result')}>Gỡ kết quả</button></div> : null}
      </section>
      {busy ? <p className="assessment-help" role="status">{busy === 'predict' ? 'Đang chạy mô hình trên máy chủ' : 'Đang đọc dữ liệu CSV'}</p> : null}
      {error ? <p className="assessment-error" role="alert">{error}</p> : null}
      {legacyAvailable ? <a className="text-link assessment-legacy" href="/legacy/" target="_blank" rel="noopener">Mở công cụ hiện tại</a> : null}
    </aside>
    <div className="assessment-content">
      <div className="demo-tabs" role="tablist" aria-label="Chế độ làm việc" onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 'map' : event.key === 'End' ? 'data' : tab === 'map' ? 'data' : 'map';
        setTab(next); (next === 'map' ? mapTab : dataTab).current?.focus();
      }}>
        <button id="map-tab" ref={mapTab} type="button" role="tab" disabled={!ready} aria-selected={tab === 'map'} aria-controls="map-panel" tabIndex={tab === 'map' ? 0 : -1} onClick={() => setTab('map')}>Bản đồ</button>
        <button id="data-tab" ref={dataTab} type="button" role="tab" disabled={!ready} aria-selected={tab === 'data'} aria-controls="data-panel" tabIndex={tab === 'data' ? 0 : -1} onClick={() => setTab('data')}>Dự đoán</button>
      </div>
      <div id="map-panel" className="demo-map-panel" role="tabpanel" aria-labelledby="map-tab" hidden={tab !== 'map'}><div><PlanIllustration variant={1} /></div><div className="demo-map-caption">Sơ đồ minh họa bố cục, phần ghép lưới đánh giá sẽ được nối ở bước tiếp theo</div></div>
      <div id="data-panel" className="demo-data-panel" role="tabpanel" aria-labelledby="data-tab" hidden={tab !== 'data'} aria-busy={Boolean(busy)}>
        <div className="table-toolbar"><div><h2>{view === 'result' && result ? 'Kết quả đánh giá' : 'Bảng dữ liệu'}</h2><p className="assessment-help">{dataset ? dataset.count.toLocaleString('vi-VN') + ' dòng' + (view === 'input' ? ', xem trước tối đa 200 dòng' : '') : 'Chưa có dữ liệu'}</p></div>
          {view === 'result' && result ? <button type="button" className="button secondary" onClick={download}>Xuất CSV</button> : null}
        </div>
        {preview && result ? <div className="assessment-table-views" role="group" aria-label="Bảng đang xem"><button type="button" aria-pressed={view === 'input'} onClick={() => setState(current => ({ ...current, view: 'input', page: 0 }))}>Dữ liệu đầu vào</button><button type="button" aria-pressed={view === 'result'} onClick={() => setState(current => ({ ...current, view: 'result', page: 0 }))}>Kết quả</button></div> : null}
        {view === 'result' && result ? <p className="assessment-help">{result.source === 'prediction' ? 'Kết quả từ phiên bản ' + result.model_version : 'Kết quả từ CSV bạn đã nạp'}</p> : null}
        {dataset ? <><div className="assessment-table-scroll"><table className="assessment-table"><caption className="sr-only">{view === 'result' ? 'Kết quả đánh giá theo từng ô đất' : 'Dữ liệu CSV đã nạp'}</caption><thead><tr>{dataset.columns.map(column => <th key={column} scope="col">{column}</th>)}</tr></thead><tbody>{visibleRows.map((row, index) => <tr key={page * 50 + index}>{dataset.columns.map(column => <td key={column}>{view === 'result' && column === 'Y' && row[column] === '' ? 'Chưa có dữ liệu' : String(row[column] ?? '')}</td>)}</tr>)}</tbody></table></div>
          <div className="assessment-pager"><button type="button" disabled={page === 0} onClick={() => setState(current => ({ ...current, page: current.page - 1 }))}>Trước</button><span>Trang {page + 1} / {pages}</span><button type="button" disabled={page + 1 >= pages} onClick={() => setState(current => ({ ...current, page: current.page + 1 }))}>Sau</button></div>
        </> : <div className="data-explanation"><h3>Chưa có dữ liệu</h3><p>Chọn CSV đầu vào hoặc nạp CSV kết quả của bạn để bắt đầu</p></div>}
      </div>
    </div>
  </div>;
}
